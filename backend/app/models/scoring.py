"""Qualification d'une opportunité (Phase 5) : son score expliqué (un seul par fiche, toujours
justifié — RB-004), les décisions GO / NO-GO prises et l'historique de ses changements de statut."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
from app.models.tender import Tender, TenderStatus


def _now() -> datetime:
    # Horodatage côté Python (comme `TenderSourceLink.collected_at`) : `now()` PostgreSQL est
    # identique pour toute une transaction, ce qui rendrait l'ordre de l'historique ambigu.
    return datetime.now(tz=UTC)


class DecisionKind(enum.StrEnum):
    go = "go"
    no_go = "no_go"


class TenderScore(UUIDMixin, Base):
    """Score de pertinence sur 100 : sous-scores déterministes (`breakdown`, un par critère) et
    justification IA avec ajustement borné. Recalculé en place : `tender_id` est unique."""

    __tablename__ = "tender_scores"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), unique=True)
    total: Mapped[float] = mapped_column(Numeric(5, 2))
    # Un élément par critère : {key, score, weight, reason, matched, missing}.
    breakdown: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    justification: Mapped[str] = mapped_column(Text)  # RB-004 : jamais vide
    ai_adjustment: Mapped[int] = mapped_column(Integer, default=0)  # borné à ± 10 par le service
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    scoring_version: Mapped[str] = mapped_column(String(16))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tender: Mapped[Tender] = relationship(back_populates="score")


class TenderDecision(UUIDMixin, Base):
    """Décision GO / NO-GO motivée ; plusieurs décisions possibles dans le temps (revirement)."""

    __tablename__ = "tender_decisions"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    decision: Mapped[DecisionKind] = mapped_column(String(8))
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(255))  # libellé lisible (email), jamais un UUID
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tender: Mapped[Tender] = relationship(back_populates="decisions")


class TenderStatusHistory(UUIDMixin, Base):
    """Une ligne par changement de statut (machine à états de la Task 5.4)."""

    __tablename__ = "tender_status_history"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[TenderStatus | None] = mapped_column(String(16))
    to_status: Mapped[TenderStatus] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tender: Mapped[Tender] = relationship(back_populates="status_history")
