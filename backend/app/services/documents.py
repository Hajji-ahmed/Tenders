"""Documents de l'entreprise : validation des envois, stockage objet, versions, archivage et
règle d'expiration RB-007 (un document expiré n'est jamais sélectionné automatiquement).

Le stockage est reçu par injection : l'endpoint passe `deps.get_storage()`, les tests la fixture
`storage`. Le service n'importe ni `deps` ni les tâches Celery (règle : tâches → services).
"""

import hashlib
import uuid
from datetime import date
from pathlib import PurePosixPath

import filetype
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.connectors.storage.base import StorageProvider, build_key
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.errors import ConflictError, ValidationError
from app.models.document import (
    CompanyDocument,
    DocumentCategory,
    DocumentKind,
    DocumentStatus,
    DocumentVersion,
    ExtractionStatus,
)
from app.services.company import CompanyService

ENTITY_KIND = "company_document"
STORAGE_PREFIX = "company"

# MIME autorisé -> extension attendue (CdC §13 : PDF, DOCX, XLSX, TXT, ZIP).
ALLOWED_MIMES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",  # MIME envoyé par les navigateurs sous Windows
}
# Métadonnées acceptées par `DocumentService.upload(**meta)` ; les valeurs None sont ignorées.
UPLOAD_META_FIELDS = frozenset({"name", "description", "issued_at", "expires_at", "tags", "status"})


def validate_upload(filename: str, data: bytes, content_type: str) -> str:
    """Contrôle type MIME, extension, taille et signature binaire (AT §18) ; renvoie le sha256 hex.

    Lève `ValidationError` (422) — jamais `ValueError`, réservé aux erreurs de programmation (500).
    """
    expected_ext = ALLOWED_MIMES.get(content_type)
    if expected_ext is None:
        raise ValidationError(
            "Type de fichier non autorisé (PDF, DOCX, XLSX, TXT, ZIP)", code="unsupported_file_type"
        )
    if PurePosixPath(filename).suffix.lower() != expected_ext:
        raise ValidationError(
            f"L'extension de « {filename} » ne correspond pas au type {content_type}",
            code="unsupported_file_type",
        )
    if not data:
        raise ValidationError("Fichier vide", code="empty_file")
    max_mb = get_settings().max_upload_mb
    if len(data) > max_mb * 1024 * 1024:
        raise ValidationError(f"Fichier trop volumineux (max {max_mb} Mo)", code="file_too_large")
    # Signature binaire réelle : un exécutable ou une image renommés en .pdf sont refusés ; un contenu
    # non reconnu (texte, octets quelconques) est accepté car TXT n'a pas de signature.
    detected = filetype.guess(data)
    if detected is not None and detected.mime not in ALLOWED_MIMES:
        raise ValidationError(
            "Le contenu du fichier ne correspond pas à un format autorisé", code="unsupported_file_type"
        )
    return hashlib.sha256(data).hexdigest()


class DocumentService:
    def __init__(self, db: Session, storage: StorageProvider, user_id: uuid.UUID | None = None):
        self.db = db
        self.storage = storage
        self.user_id = user_id

    def upload(
        self, *, filename: str, data: bytes, content_type: str, category: DocumentCategory, **meta
    ) -> CompanyDocument:
        """Valide, stocke et enregistre un nouveau document (version 1).

        `meta` : `name`, `description`, `issued_at`, `expires_at`, `tags`, `status` (cf. UPLOAD_META_FIELDS).
        Un doublon exact (même sha256 et même catégorie, non archivé) est refusé par `ConflictError`.
        """
        unknown = set(meta) - UPLOAD_META_FIELDS
        if unknown:
            raise TypeError(f"Métadonnées inconnues pour upload() : {sorted(unknown)}")
        sha = validate_upload(filename, data, content_type)
        company = CompanyService.get_or_create(self.db)
        duplicate = self.db.scalar(
            select(CompanyDocument).where(
                CompanyDocument.company_id == company.id,
                CompanyDocument.sha256 == sha,
                CompanyDocument.category == category,
                CompanyDocument.status != DocumentStatus.archived,
            )
        )
        if duplicate is not None:
            raise ConflictError(
                f"Document identique déjà présent : {duplicate.name}", code="duplicate_document"
            )
        key = build_key(STORAGE_PREFIX, sha, filename)
        self.storage.put(key, data, content_type)
        fields = {k: v for k, v in meta.items() if v is not None}
        name = (fields.pop("name", None) or filename)[:255]
        doc = CompanyDocument(
            company_id=company.id,
            name=name,
            category=category,
            storage_key=key,
            mime_type=content_type,
            size_bytes=len(data),
            sha256=sha,
            **fields,
        )
        self.db.add(doc)
        self.db.flush()
        self._add_version(doc, changelog=None)
        record_audit(
            self.db,
            action="document.uploaded",
            entity_kind=ENTITY_KIND,
            entity_id=doc.id,
            payload={"name": doc.name, "category": str(category), "size_bytes": doc.size_bytes},
            user_id=self.user_id,
        )
        self.db.flush()
        return doc

    def new_version(
        self,
        doc: CompanyDocument,
        *,
        filename: str,
        data: bytes,
        content_type: str,
        changelog: str | None = None,
    ) -> CompanyDocument:
        """Remplace le fichier courant (version + 1) ; l'ancienne clé reste référencée par sa
        `DocumentVersion`. Le statut n'est pas modifié : prolonger `expires_at` relève du PATCH, la
        tâche `refresh_document_expiry` remet ensuite le document en `valid`."""
        if doc.status == DocumentStatus.archived:
            raise ConflictError(
                "Document archivé : impossible d'ajouter une version", code="document_archived"
            )
        sha = validate_upload(filename, data, content_type)
        key = build_key(STORAGE_PREFIX, sha, filename)
        self.storage.put(key, data, content_type)
        doc.version += 1
        doc.storage_key = key
        doc.sha256 = sha
        doc.size_bytes = len(data)
        doc.mime_type = content_type
        doc.extraction_status = ExtractionStatus.pending
        doc.extracted_text = None
        self._add_version(doc, changelog=changelog)
        record_audit(
            self.db,
            action="document.versioned",
            entity_kind=ENTITY_KIND,
            entity_id=doc.id,
            payload={"version": doc.version, "changelog": changelog},
            user_id=self.user_id,
        )
        self.db.flush()
        return doc

    def versions(self, doc: CompanyDocument) -> list[DocumentVersion]:
        q = (
            select(DocumentVersion)
            .where(
                DocumentVersion.document_kind == DocumentKind.company,
                DocumentVersion.document_id == doc.id,
            )
            .order_by(DocumentVersion.version_number)
        )
        return list(self.db.scalars(q))

    def archive(self, doc: CompanyDocument) -> None:
        """Archivage logique (le fichier reste dans le stockage) ; idempotent."""
        if doc.status == DocumentStatus.archived:
            return
        doc.status = DocumentStatus.archived
        record_audit(
            self.db,
            action="document.archived",
            entity_kind=ENTITY_KIND,
            entity_id=doc.id,
            payload={"name": doc.name},
            user_id=self.user_id,
        )
        self.db.flush()

    def _add_version(self, doc: CompanyDocument, *, changelog: str | None) -> DocumentVersion:
        version = DocumentVersion(
            document_kind=DocumentKind.company,
            document_id=doc.id,
            version_number=doc.version,
            storage_key=doc.storage_key,
            sha256=doc.sha256,
            author=str(self.user_id) if self.user_id else None,
            changelog=changelog,
        )
        self.db.add(version)
        return version


def refresh_expiry_statuses(db: Session) -> int:
    """RB-007 : `valid` → `expired` quand `expires_at` est dépassée ; `expired` → `valid` quand la date
    a été prolongée ou retirée. `draft` et `archived` ne bougent jamais. Renvoie le nombre de lignes
    modifiées. Appelée chaque nuit par la tâche beat `refresh_document_expiry` (ne commite pas)."""
    today = date.today()
    expired = db.execute(
        update(CompanyDocument)
        .where(CompanyDocument.status == DocumentStatus.valid, CompanyDocument.expires_at < today)
        .values(status=DocumentStatus.expired)
        .execution_options(synchronize_session="fetch")
    )
    revalidated = db.execute(
        update(CompanyDocument)
        .where(
            CompanyDocument.status == DocumentStatus.expired,
            or_(CompanyDocument.expires_at.is_(None), CompanyDocument.expires_at >= today),
        )
        .values(status=DocumentStatus.valid)
        .execution_options(synchronize_session="fetch")
    )
    return expired.rowcount + revalidated.rowcount
