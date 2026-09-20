"""Analyse structurée du dossier de consultation (Phase 6) : une analyse par opportunité (écrasée à
chaque nouvelle lecture) et ses critères d'évaluation, chacun avec sa page source."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
from app.models.tender import Tender


def _now() -> datetime:
    return datetime.now(tz=UTC)


class TenderAnalysis(UUIDMixin, Base):
    __tablename__ = "tender_analyses"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), unique=True)
    object: Mapped[str] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(String(255))
    reference: Mapped[str | None] = mapped_column(String(128))
    budget: Mapped[str | None] = mapped_column(String(255))
    duration: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    key_dates: Mapped[list] = mapped_column(JSON, default=list)  # [{label, date, source_page}]
    deliverables: Mapped[list] = mapped_column(JSON, default=list)
    requested_documents: Mapped[list] = mapped_column(JSON, default=list)  # [{name, mandatory, source_page}]
    eligibility_conditions: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tender: Mapped[Tender] = relationship(back_populates="analysis")


class TenderCriterion(UUIDMixin, Base):
    __tablename__ = "tender_criteria"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # ordre du règlement
    name: Mapped[str] = mapped_column(String(255))
    weight: Mapped[float | None] = mapped_column(Numeric(6, 2))
    description: Mapped[str | None] = mapped_column(Text)
    source_page: Mapped[int | None] = mapped_column(Integer)

    tender: Mapped[Tender] = relationship(back_populates="criteria")
