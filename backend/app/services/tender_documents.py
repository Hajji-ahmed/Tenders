"""Pièces d'un appel d'offres (DCE, règlement, annexes) : enregistrement des URL découvertes,
téléchargement résilient — un document en échec porte son erreur, jamais d'exception — et dépôt
manuel validé comme un document d'entreprise. Le stockage et le client HTTP sont injectés."""

import hashlib
from pathlib import PurePosixPath

import filetype  # type: ignore[import-untyped]
import httpx
from sqlalchemy.orm import Session

from app.connectors.storage.base import StorageProvider, build_key
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import DownloadStatus, Tender, TenderDocument
from app.services.documents import ALLOWED_MIMES, validate_upload
from app.services.normalize import document_name

log = get_logger("tender_documents")

USER_AGENT = "tender-ai/1.0 (+https://innosustain.africa)"
DOWNLOAD_TIMEOUT = 60.0
CHUNK = 64 * 1024


def build_download_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        transport=transport,
        follow_redirects=True,
        timeout=DOWNLOAD_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )


class DownloadError(Exception):
    """Motif lisible d'un téléchargement refusé (statut HTTP, type, taille)."""


def _mime_of(header: str, data: bytes) -> str | None:
    """Type MIME accepté : l'en-tête `Content-Type` s'il est autorisé, sinon la signature binaire
    (`filetype`) ; None si la pièce n'est pas d'un format pris en charge."""
    declared = header.split(";")[0].strip().lower()
    if declared in ALLOWED_MIMES:
        return declared
    detected = filetype.guess(data)
    if detected is not None and detected.mime in ALLOWED_MIMES:
        return detected.mime
    if declared == "text/plain":
        return declared
    return None


class TenderDocumentService:
    def __init__(self, db: Session, storage: StorageProvider, http: httpx.Client | None = None):
        self.db = db
        self.storage = storage
        self.http = http or build_download_client()

    # --- enregistrement -----------------------------------------------------------------------

    def register_urls(self, tender: Tender, urls: list[str]) -> list[TenderDocument]:
        """Une pièce `pending` par URL nouvelle (idempotent) ; renvoie les pièces de ces URL, dans
        l'ordre, doublons de la liste écartés."""
        known = {d.source_url: d for d in tender.documents if d.source_url}
        result: list[TenderDocument] = []
        for url in dict.fromkeys(u.strip() for u in urls if u and u.strip()):
            doc = known.get(url)
            if doc is None:
                doc = TenderDocument(name=document_name(url), source_url=url)
                tender.documents.append(doc)
                known[url] = doc
            result.append(doc)
        self.db.flush()
        return result

    # --- téléchargement -----------------------------------------------------------------------

    def download(self, doc: TenderDocument) -> TenderDocument:
        """Télécharge la pièce dans le stockage ; `done` ou `failed` + `error`, sans lever."""
        if doc.download_status == DownloadStatus.done or not doc.source_url:
            return doc
        try:
            data, header = self._fetch(doc.source_url)
            mime = _mime_of(header, data)
            if mime is None:
                raise DownloadError(f"Type non pris en charge ({header.split(';')[0].strip() or 'inconnu'})")
            self._store(doc, data, mime, doc.name)
            doc.download_status = DownloadStatus.done
            doc.error = None
            log.info("tender_document.downloaded", document_id=str(doc.id), size=len(data), mime=mime)
        except (DownloadError, httpx.HTTPError) as e:
            doc.download_status = DownloadStatus.failed
            doc.error = (f"{type(e).__name__}: {e}" if isinstance(e, httpx.HTTPError) else str(e))[:2000]
            log.warning(
                "tender_document.failed", document_id=str(doc.id), url=doc.source_url, error=doc.error
            )
        self.db.flush()
        return doc

    def _fetch(self, url: str) -> tuple[bytes, str]:
        max_bytes = get_settings().max_upload_mb * 1024 * 1024
        with self.http.stream("GET", url) as response:
            if not 200 <= response.status_code < 300:
                raise DownloadError(f"HTTP {response.status_code}")
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise DownloadError(f"Fichier trop volumineux (max {get_settings().max_upload_mb} Mo)")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise DownloadError(f"Fichier trop volumineux (max {get_settings().max_upload_mb} Mo)")
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data:
                raise DownloadError("Fichier vide")
            return data, response.headers.get("content-type", "")

    # --- dépôt manuel -------------------------------------------------------------------------

    def upload_manual(
        self, tender: Tender, *, filename: str, data: bytes, content_type: str, user_id=None
    ) -> TenderDocument:
        """Pièce déposée par l'utilisateur : mêmes contrôles que les documents d'entreprise
        (type, extension, taille, signature) ; `ValidationError` sinon."""
        validate_upload(filename, data, content_type)
        doc = TenderDocument(name=filename[:255], source_url=None)
        tender.documents.append(doc)
        self.db.flush()  # `tender_id` nécessaire à la clé de stockage
        self._store(doc, data, content_type, filename)
        doc.download_status = DownloadStatus.done
        self.db.flush()
        record_audit(
            self.db,
            action="tender_document.uploaded",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"name": doc.name, "size_bytes": doc.size_bytes},
            user_id=user_id,
        )
        self.db.flush()
        return doc

    # --- commun -------------------------------------------------------------------------------

    def _store(self, doc: TenderDocument, data: bytes, mime: str, filename: str) -> None:
        sha = hashlib.sha256(data).hexdigest()
        ext = ALLOWED_MIMES.get(mime, "")
        name = filename if PurePosixPath(filename).suffix.lower() == ext else f"{filename}{ext}"
        key = build_key(f"tenders/{doc.tender_id}", sha, name)
        self.storage.put(key, data, mime)
        doc.storage_key = key
        doc.mime_type = mime
        doc.size_bytes = len(data)
        doc.sha256 = sha
