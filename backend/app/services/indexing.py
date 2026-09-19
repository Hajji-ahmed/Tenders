"""Indexation d'un document (pièce d'appel d'offres ou document d'entreprise) : lecture dans le
stockage, extraction du texte (pages), découpage, vectorisation par lots, remplacement des anciens
morceaux. Un échec d'extraction est enregistré sur le document (`failed` + motif) sans lever :
l'appelant décide (le job rend un résultat avec `error`)."""

from typing import Literal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.connectors.storage.base import StorageProvider
from app.core.logging import get_logger
from app.models import CompanyDocument, DocumentChunk, ExtractionStatus, TenderDocument
from app.services.chunking import chunk_pages
from app.services.extraction import ExtractedDocument, ExtractionError, extract

log = get_logger("indexing")

Kind = Literal["tender_document", "company_document"]
PAGE_SEPARATOR = "\f"  # comme pdftotext : `extracted_text.split("\f")` redonne les pages
EMBED_BATCH = 64


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class IndexingService:
    def __init__(self, db: Session, storage: StorageProvider, embeddings: EmbeddingProvider):
        self.db = db
        self.storage = storage
        self.embeddings = embeddings
        self.last_error: str | None = None

    def index(self, kind: Kind, doc: TenderDocument | CompanyDocument) -> int:
        """Renvoie le nombre de morceaux indexés (0 et `last_error` renseigné en cas d'échec)."""
        self.last_error = None
        try:
            documents = self._extract(doc)
        except ExtractionError as e:
            return self._fail(doc, str(e))

        pages_total = sum(len(d.pages) for d in documents)
        doc.extracted_text = PAGE_SEPARATOR.join(p.text for d in documents for p in d.pages)
        doc.page_count = pages_total

        self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.owner_kind == kind, DocumentChunk.owner_id == doc.id)
        )
        rows = self._build_chunks(kind, doc, documents)
        for start in range(0, len(rows), EMBED_BATCH):
            batch = rows[start : start + EMBED_BATCH]
            vectors = self.embeddings.embed([r.content for r in batch])
            for row, vector in zip(batch, vectors, strict=True):
                row.embedding = vector
        self.db.add_all(rows)
        doc.extraction_status = ExtractionStatus.done
        if isinstance(doc, TenderDocument):
            doc.error = None
        self.db.flush()
        log.info("indexing.done", kind=kind, document_id=str(doc.id), chunks=len(rows), pages=pages_total)
        return len(rows)

    def _extract(self, doc: TenderDocument | CompanyDocument) -> list[ExtractedDocument]:
        if not doc.storage_key:
            raise ExtractionError("Fichier absent du stockage")
        try:
            data = self.storage.get(doc.storage_key)
        except Exception as e:  # noqa: BLE001 — clé inconnue, stockage indisponible
            raise ExtractionError("Fichier absent du stockage") from e
        return extract(data, doc.mime_type or "application/octet-stream", doc.name)

    def _build_chunks(
        self, kind: Kind, doc: TenderDocument | CompanyDocument, documents: list[ExtractedDocument]
    ) -> list[DocumentChunk]:
        rows: list[DocumentChunk] = []
        for extracted in documents:
            inner = extracted.metadata.get("inner_filename")
            for chunk in chunk_pages(extracted.pages):
                rows.append(
                    DocumentChunk(
                        owner_kind=kind,
                        owner_id=doc.id,
                        tender_id=doc.tender_id if isinstance(doc, TenderDocument) else None,
                        company_document_id=doc.id if isinstance(doc, CompanyDocument) else None,
                        chunk_index=len(rows),
                        page=chunk.page,
                        section=chunk.section,
                        content=chunk.text,
                        token_count=_estimate_tokens(chunk.text),
                        meta={"inner_filename": inner} if inner else {},
                    )
                )
        return rows

    def _fail(self, doc: TenderDocument | CompanyDocument, message: str) -> int:
        self.last_error = message
        doc.extraction_status = ExtractionStatus.failed
        if isinstance(doc, TenderDocument):
            doc.error = message[:2000]
        self.db.flush()
        log.warning("indexing.failed", document_id=str(doc.id), error=message)
        return 0
