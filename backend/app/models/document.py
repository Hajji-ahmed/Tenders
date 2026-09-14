"""Documents internes de l'entreprise (présentation, certifications, attestations, CV…) et
historique de versions. Les fichiers vivent dans le stockage objet ; ici : métadonnées, hash,
statut et expiration (RB-007 : un document expiré n'est jamais sélectionné automatiquement)."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DocumentCategory(enum.StrEnum):
    presentation = "presentation"
    certification = "certification"
    attestation = "attestation"
    reference = "reference"
    cv = "cv"
    administratif = "administratif"
    financier = "financier"
    juridique = "juridique"
    template = "template"
    autre = "autre"


class DocumentStatus(enum.StrEnum):
    draft = "draft"
    valid = "valid"
    expired = "expired"
    archived = "archived"


class ExtractionStatus(enum.StrEnum):
    pending = "pending"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class DocumentKind(enum.StrEnum):
    company = "company"
    application = "application"


class CompanyDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_documents"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[DocumentCategory] = mapped_column(String(32), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[DocumentStatus] = mapped_column(String(16), default=DocumentStatus.valid, index=True)
    issued_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(String(16), default=ExtractionStatus.pending)
    extracted_text: Mapped[str | None] = mapped_column(Text)

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at < date.today()

    @property
    def is_usable(self) -> bool:
        """RB-007 : seul un document valide et non expiré peut être sélectionné automatiquement."""
        return self.status == DocumentStatus.valid and not self.is_expired


class DocumentVersion(UUIDMixin, Base):
    """Une ligne par version d'un document entreprise ou d'un document de candidature généré.
    `document_id` est polymorphe (pas de clé étrangère) : le couple (document_kind, document_id)
    identifie la cible."""

    __tablename__ = "document_versions"

    document_kind: Mapped[DocumentKind] = mapped_column(String(16))
    document_id: Mapped[uuid.UUID] = mapped_column(index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    author: Mapped[str | None] = mapped_column(String(255))
    changelog: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict | None] = mapped_column(JSON)  # sections d'un document généré (Phase 10)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
