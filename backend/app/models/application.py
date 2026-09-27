"""Dossier de candidature (Phase 9) : une `Application` par appel d'offres, les documents qu'elle
contient et leurs sections rédigées.

Chaque section garde ce qui a servi à l'écrire (`sources`) et ce qui a manqué (`missing_info`) : une
candidature se relit, et rien de ce que le modèle avance ne doit être invérifiable (RB-005). La
validation humaine (Phase 10) travaille sur ces mêmes lignes — `status` par section et par document."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.template import DocumentType, Template
from app.models.tender import Tender


def _now() -> datetime:
    """Horodatage côté Python : `now()` PostgreSQL est constant sur toute une transaction."""
    return datetime.now(tz=UTC)


class ApplicationStatus(enum.StrEnum):
    draft = "draft"
    generating = "generating"
    review = "review"
    validated = "validated"
    ready = "ready"
    submitted = "submitted"
    archived = "archived"


class AppDocStatus(enum.StrEnum):
    pending = "pending"
    generating = "generating"
    draft = "draft"
    validated = "validated"
    rejected = "rejected"
    failed = "failed"


class SectionStatus(enum.StrEnum):
    generated = "generated"
    edited = "edited"
    validated = "validated"
    rejected = "rejected"


class Application(UUIDMixin, TimestampMixin, Base):
    """Le dossier préparé pour un appel d'offres : un seul par fiche (`tender_id` unique)."""

    __tablename__ = "applications"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), unique=True)
    status: Mapped[ApplicationStatus] = mapped_column(String(16), default=ApplicationStatus.draft, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tender: Mapped[Tender] = relationship(back_populates="application")
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ApplicationDocument.created_at",
    )


class ApplicationDocument(UUIDMixin, TimestampMixin, Base):
    """Un document du dossier, issu d'un modèle. `warnings` retient ce que la génération a signalé
    (faits absents, sections vides) : le relire, c'est d'abord lire ça."""

    __tablename__ = "application_documents"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("templates.id", ondelete="SET NULL"))
    document_type: Mapped[DocumentType] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[AppDocStatus] = mapped_column(String(16), default=AppDocStatus.pending, index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)  # 0 : jamais généré
    export_storage_key: Mapped[str | None] = mapped_column(String(512))  # DOCX exporté (9.5)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    # Pour un document répétable : l'expert ou le projet qu'il présente (CV, fiche de référence).
    subject_kind: Mapped[str | None] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID | None] = mapped_column()

    application: Mapped[Application] = relationship(back_populates="documents")
    template: Mapped[Template | None] = relationship()
    sections: Mapped[list["ApplicationSection"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ApplicationSection.position",
    )


class ApplicationSection(UUIDMixin, TimestampMixin, Base):
    """Une section rédigée : son texte (Markdown), ce sur quoi elle s'appuie et ce qui lui manque."""

    __tablename__ = "application_sections"
    __table_args__ = (UniqueConstraint("document_id", "key", name="uq_section_document_key"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_documents.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)
    content_md: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SectionStatus] = mapped_column(String(16), default=SectionStatus.generated, index=True)
    # Sources citées par la génération : [{kind, id, label, page}] — même forme que les preuves (8.4).
    sources: Mapped[list] = mapped_column(JSON, default=list)
    # Ce que le modèle n'a pas trouvé et qu'il ne doit pas inventer : [{field, reason}] (RB-005).
    missing_info: Mapped[list] = mapped_column(JSON, default=list)
    comment: Mapped[str | None] = mapped_column(Text)  # motif d'un rejet, note de relecture
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)

    document: Mapped[ApplicationDocument] = relationship(back_populates="sections")
