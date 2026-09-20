"""Extraction de texte des pièces (CdC §13) : PDF page par page (PyMuPDF), DOCX (paragraphes et
tableaux dans l'ordre du document), XLSX (une « page » par feuille), TXT, ZIP (plusieurs documents,
un niveau de récursion). Pas d'OCR en MVP : un PDF scanné est signalé, pas deviné. Toute erreur
de lecture devient une `ExtractionError` au message lisible."""

import io
import zipfile
from pathlib import PurePosixPath

import openpyxl  # type: ignore[import-untyped]
import pymupdf
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TXT = "text/plain"
ZIP = "application/zip"
MIME_BY_EXTENSION = {".pdf": PDF, ".docx": DOCX, ".xlsx": XLSX, ".txt": TXT, ".zip": ZIP}

MAX_SHEET_ROWS = 2_000
MAX_ZIP_MEMBER_BYTES = 50 * 1024 * 1024
MAX_ZIP_DEPTH = 1


class ExtractedPage(BaseModel):
    number: int
    text: str


class ExtractedDocument(BaseModel):
    filename: str
    mime_type: str
    pages: list[ExtractedPage]
    char_count: int
    # ZIP : `inner_filename`, `skipped` (entrées ignorées), `failed` (entrées illisibles → motif) ;
    # XLSX : `sheets`, `truncated_sheets`.
    metadata: dict = Field(default_factory=dict)


class ExtractionError(Exception):
    """La pièce ne peut pas être lue (format, protection, scan, archive corrompue)."""


def _document(filename: str, mime_type: str, pages: list[ExtractedPage], **metadata) -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename,
        mime_type=mime_type,
        pages=pages,
        char_count=sum(len(p.text) for p in pages),
        metadata=metadata,
    )


# --- formats ------------------------------------------------------------------------------------


def extract_pdf(data: bytes, filename: str) -> ExtractedDocument:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:  # noqa: BLE001 — PyMuPDF lève des exceptions génériques
        raise ExtractionError("PDF protégé ou illisible") from e
    try:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ExtractionError("PDF protégé ou illisible")
        pages = [
            ExtractedPage(number=number + 1, text=doc[number].get_text("text").strip())
            for number in range(doc.page_count)
        ]
    except ExtractionError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ExtractionError("PDF protégé ou illisible") from e
    finally:
        doc.close()
    if not pages or all(not p.text for p in pages):
        raise ExtractionError("PDF sans texte (scan) — OCR non supporté en MVP")
    return _document(filename, PDF, pages)


def _docx_blocks(document) -> list[str]:
    """Paragraphes et tableaux dans l'ordre du corps ; les cellules d'une ligne sont jointes par ` | `."""
    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, document).text.strip()
            if text:
                blocks.append(text)
        elif child.tag == qn("w:tbl"):
            for row in Table(child, document).rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    blocks.append(" | ".join(cells))
    return blocks


def extract_docx(data: bytes, filename: str) -> ExtractedDocument:
    try:
        document = Document(io.BytesIO(data))
        blocks = _docx_blocks(document)
    except Exception as e:  # noqa: BLE001
        raise ExtractionError("DOCX illisible") from e
    return _document(filename, DOCX, [ExtractedPage(number=1, text="\n".join(blocks))])


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def extract_xlsx(data: bytes, filename: str) -> ExtractedDocument:
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ExtractionError("XLSX illisible") from e
    pages: list[ExtractedPage] = []
    truncated: list[str] = []
    try:
        for index, sheet in enumerate(workbook.worksheets):
            lines: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [_cell(v) for v in row]
                if not any(cells):
                    continue
                if len(lines) >= MAX_SHEET_ROWS:
                    truncated.append(sheet.title)
                    break
                lines.append("\t".join(cells).rstrip("\t"))
            pages.append(ExtractedPage(number=index + 1, text="\n".join(lines)))
        sheets = [s.title for s in workbook.worksheets]
    finally:
        workbook.close()
    return _document(filename, XLSX, pages, sheets=sheets, truncated_sheets=truncated)


def extract_txt(data: bytes, filename: str) -> ExtractedDocument:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return _document(filename, TXT, [ExtractedPage(number=1, text=text.strip())])


def extract_zip(data: bytes, filename: str, *, depth: int = 0) -> list[ExtractedDocument]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        members = archive.infolist()
    except (zipfile.BadZipFile, OSError) as e:
        raise ExtractionError("Archive illisible") from e
    documents: list[ExtractedDocument] = []
    skipped: list[str] = []
    failed: dict[str, str] = {}
    with archive:
        for member in members:
            name = member.filename
            if name.endswith("/"):
                continue
            if ".." in PurePosixPath(name).parts or name.startswith(("/", "\\")):
                raise ExtractionError(f"Archive suspecte : chemin « {name} » (../ interdit)")
            inner_name = f"{filename}/{name}" if depth else name
            mime = MIME_BY_EXTENSION.get(PurePosixPath(name).suffix.lower())
            if (
                mime is None
                or member.file_size > MAX_ZIP_MEMBER_BYTES
                or (mime == ZIP and depth >= MAX_ZIP_DEPTH)
            ):
                skipped.append(inner_name)
                continue
            try:
                content = archive.read(member)
                if mime == ZIP:
                    documents.extend(extract_zip(content, inner_name, depth=depth + 1))
                else:
                    doc = _extract_one(content, mime, inner_name)
                    doc.metadata["inner_filename"] = inner_name
                    documents.append(doc)
            except ExtractionError as e:
                failed[inner_name] = str(e)
    if not documents:
        raise ExtractionError("Aucun document exploitable dans l'archive")
    for doc in documents:
        if "skipped" not in doc.metadata:  # les documents d'une archive imbriquée gardent son rapport
            doc.metadata["skipped"] = skipped
            doc.metadata["failed"] = failed
    return documents


# --- point d'entrée -----------------------------------------------------------------------------


def _extract_one(data: bytes, mime_type: str, filename: str) -> ExtractedDocument:
    match mime_type:
        case "application/pdf":
            return extract_pdf(data, filename)
        case m if m == DOCX:
            return extract_docx(data, filename)
        case m if m == XLSX:
            return extract_xlsx(data, filename)
        case "text/plain":
            return extract_txt(data, filename)
    raise ExtractionError(f"Format non pris en charge ({mime_type})")


def extract(data: bytes, mime_type: str, filename: str) -> list[ExtractedDocument]:
    """Texte d'une pièce ; une archive ZIP donne un document par membre lisible (un niveau)."""
    mime = mime_type.split(";")[0].strip().lower()
    if mime in ("application/zip", "application/x-zip-compressed"):
        return extract_zip(data, filename)
    return [_extract_one(data, mime, filename)]
