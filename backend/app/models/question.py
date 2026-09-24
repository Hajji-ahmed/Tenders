"""Questions ciblées (Phase 7, FR-014 / FR-015) : quand le moteur d'éligibilité ne peut pas conclure
sur une exigence (information manquante, à vérifier, non-conformité tenant peut-être à un profil
incomplet), une question précise est posée à l'utilisateur ; sa réponse (une par question, la
dernière remplace) est reprise par le moteur comme preuve prioritaire."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.requirement import Priority, TenderRequirement
from app.models.tender import Tender


class QuestionStatus(enum.StrEnum):
    open = "open"
    answered = "answered"
    skipped = "skipped"


class Question(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tender_requirements.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(String(16), default=Priority.IMPORTANTE)
    status: Mapped[QuestionStatus] = mapped_column(String(16), default=QuestionStatus.open, index=True)

    tender: Mapped[Tender] = relationship(back_populates="questions")
    requirement: Mapped[TenderRequirement] = relationship(back_populates="questions")
    answer: Mapped["QuestionAnswer | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )

    # Exposés par l'API : charger `requirement` avec selectinload en liste.
    @property
    def requirement_code(self) -> str:
        return self.requirement.code

    @property
    def requirement_status(self) -> str:
        return str(self.requirement.status)

    @property
    def is_mandatory(self) -> bool:
        return self.requirement.is_mandatory


class QuestionAnswer(UUIDMixin, Base):
    __tablename__ = "question_answers"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True
    )
    answer: Mapped[str] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    question: Mapped[Question] = relationship(back_populates="answer")

    @property
    def text(self) -> str:
        """Contrat `AnswerLike` du moteur d'éligibilité."""
        return self.answer
