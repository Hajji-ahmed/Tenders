"""Exigences d'un appel d'offres (Phase 7) : extraites des pièces avec un code stable par catégorie
(`TECH-001`, `ADM-001`…), une priorité, une source (pièce, page, extrait) et un statut d'éligibilité
posé par le moteur (7.2) ou à la main (`manual_status` : conservé lors d'une ré-extraction)."""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.tender import Tender, TenderDocument

if TYPE_CHECKING:
    from app.models.question import Question


class RequirementCategory(enum.StrEnum):
    administrative = "administrative"
    technique = "technique"
    financiere = "financiere"
    juridique = "juridique"
    experience = "experience"
    equipe = "equipe"
    certification = "certification"
    methodologie = "methodologie"
    autre = "autre"


CODE_PREFIX: dict[RequirementCategory, str] = {
    RequirementCategory.administrative: "ADM",
    RequirementCategory.technique: "TECH",
    RequirementCategory.financiere: "FIN",
    RequirementCategory.juridique: "JUR",
    RequirementCategory.experience: "EXP",
    RequirementCategory.equipe: "EQU",
    RequirementCategory.certification: "CERT",
    RequirementCategory.methodologie: "METH",
    RequirementCategory.autre: "AUT",
}


class RequirementStatus(enum.StrEnum):
    CONFORME = "CONFORME"
    A_VERIFIER = "A_VERIFIER"
    NON_CONFORME = "NON_CONFORME"
    INFO_MANQUANTE = "INFO_MANQUANTE"


class Priority(enum.StrEnum):
    CRITIQUE = "CRITIQUE"
    IMPORTANTE = "IMPORTANTE"
    FACULTATIVE = "FACULTATIVE"


class TenderRequirement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tender_requirements"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16))
    category: Mapped[RequirementCategory] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_required: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(String(16), default=Priority.IMPORTANTE)
    status: Mapped[RequirementStatus] = mapped_column(
        String(16), default=RequirementStatus.A_VERIFIER, index=True
    )
    justification: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # [{kind, id, label}] (moteur 7.2)
    manual_status: Mapped[bool] = mapped_column(Boolean, default=False)  # statut saisi à la main
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tender_documents.id", ondelete="SET NULL")
    )
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_excerpt: Mapped[str | None] = mapped_column(Text)

    tender: Mapped[Tender] = relationship(back_populates="requirements")
    source_document: Mapped[TenderDocument | None] = relationship()
    # Phase 7 (models/question) : les questions posées pour cette exigence, plus anciennes d'abord.
    questions: Mapped[list["Question"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Question.created_at",
    )

    @property
    def source_document_name(self) -> str | None:
        return self.source_document.name if self.source_document is not None else None
