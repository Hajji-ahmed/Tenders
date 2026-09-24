"""Questions ciblées (FR-014 / FR-015) : pour chaque exigence que les règles n'ont pu trancher —
information manquante, à vérifier, ou non-conformité qui peut tenir à un profil incomplet — et qui
n'a ni question en cours ni réponse déjà donnée, le modèle formule UNE question précise à partir de
l'exigence et de ce que l'entreprise possède (repli : question générique si le modèle échoue).
Obligatoire ⇒ priorité CRITIQUE. Répondre ré-évalue l'exigence liée (la réponse prime sur les
règles), rafraîchit le résumé d'éligibilité et le score ; ignorer ferme la question."""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLMProvider
from app.ai.outputs import QuestionOutput
from app.ai.prompts import question_generate
from app.core import deps
from app.core.audit import record_audit
from app.core.logging import get_logger
from app.models import (
    CompanyDocument,
    Priority,
    Question,
    QuestionAnswer,
    QuestionStatus,
    RequirementStatus,
    Tender,
    TenderRequirement,
)
from app.services.company import CompanyService
from app.services.eligibility import EligibilityEngine

log = get_logger("questions")

NEEDS_QUESTION = (
    RequirementStatus.INFO_MANQUANTE,
    RequirementStatus.A_VERIFIER,
    RequirementStatus.NON_CONFORME,
)
PENDING = (QuestionStatus.open, QuestionStatus.skipped)  # une question ignorée n'est pas reposée
PRIORITY_RANK = {Priority.CRITIQUE: 0, Priority.IMPORTANTE: 1, Priority.FACULTATIVE: 2}


def fallback_question(req: TenderRequirement) -> str:
    """Sans modèle (quota, réseau) : une question générique mais complète — une information
    manquante ne reste jamais sans question."""
    text = f"L'appel d'offres exige : « {req.description} »."
    if req.justification:
        text += f" {req.justification.rstrip('.')}."
    text += " Pouvez-vous confirmer que l'entreprise y satisfait"
    if req.evidence_required:
        text += f" et fournir la preuve attendue ({req.evidence_required})"
    return text + " ?"


def needs_question(req: TenderRequirement, pending: set[UUID]) -> bool:
    if req.status not in NEEDS_QUESTION or req.manual_status or req.id in pending:
        return False
    # Jugée sur une réponse de l'utilisateur : il a déjà dit ce qu'il savait.
    return not any(e.get("kind") == "answer" for e in (req.evidence or []))


class QuestionService:
    def __init__(self, db: Session, llm: LLMProvider | None = None):
        self.db = db
        self.llm = llm or deps.get_llm()

    def generate(self, tender: Tender) -> list[Question]:
        company = CompanyService.get_or_create(self.db)
        documents = list(
            self.db.scalars(select(CompanyDocument).where(CompanyDocument.company_id == company.id))
        )
        pending = {q.requirement_id for q in tender.questions if q.status in PENDING}
        created: list[Question] = []
        for req in tender.requirements:
            if not needs_question(req, pending):
                continue
            output = self._ask(tender, req, company, documents)
            text = output.text.strip() if output and output.text.strip() else fallback_question(req)
            priority = output.priority if output else req.priority
            if req.is_mandatory:
                priority = Priority.CRITIQUE
            question = Question(tender=tender, requirement=req, text=text, priority=priority)
            self.db.add(question)  # l'affectation `tender=` seule ne l'ajoute pas (SQLAlchemy 2)
            created.append(question)
        self.db.flush()
        record_audit(
            self.db,
            action="tender.questions_generated",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"created": len(created), "open": self.open_count(tender)},
        )
        self.db.flush()
        log.info("questions.generated", tender_id=str(tender.id), created=len(created))
        return created

    def _ask(self, tender: Tender, req: TenderRequirement, company, documents) -> QuestionOutput | None:
        try:
            return self.llm.structured(
                system=question_generate.SYSTEM,
                user=question_generate.user_prompt(tender, req, company, documents),
                output=QuestionOutput,
                tier="fast",
            )
        except Exception as e:  # noqa: BLE001 — quota, réseau, refus : question de repli
            log.warning("questions.model_failed", code=req.code, error=f"{type(e).__name__}: {e}")
            return None

    def answer(self, question: Question, text: str, user_id: UUID | None = None) -> QuestionAnswer:
        now = datetime.now(tz=UTC)
        if question.answer is None:
            question.answer = QuestionAnswer(answer=text, answered_at=now)
        else:  # une seule réponse par question : la nouvelle remplace
            question.answer.answer, question.answer.answered_at = text, now
        question.status = QuestionStatus.answered
        req, tender = question.requirement, question.tender
        engine = EligibilityEngine(self.db, CompanyService.get_or_create(self.db), llm=self.llm)
        engine.tender = tender
        engine.apply(req, engine.judge(req, [question.answer]))
        engine.refresh(tender)
        record_audit(
            self.db,
            action="question.answered",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"code": req.code, "status": str(req.status)},
            user_id=user_id,
        )
        self.db.flush()
        return question.answer

    def skip(self, question: Question, user_id: UUID | None = None) -> Question:
        question.status = QuestionStatus.skipped
        record_audit(
            self.db,
            action="question.skipped",
            entity_kind="tender",
            entity_id=question.tender_id,
            payload={"code": question.requirement.code},
            user_id=user_id,
        )
        self.db.flush()
        return question

    @staticmethod
    def open_count(tender: Tender) -> int:
        return sum(1 for q in tender.questions if q.status == QuestionStatus.open)

    @staticmethod
    def answers_by_requirement(tender: Tender) -> dict[UUID, list[QuestionAnswer]]:
        """Réponses données, par exigence, de la plus ancienne à la plus récente (la dernière prime
        dans `EligibilityEngine.judge`)."""
        answers: dict[UUID, list[QuestionAnswer]] = defaultdict(list)
        for q in tender.questions:
            if q.status == QuestionStatus.answered and q.answer is not None:
                answers[q.requirement_id].append(q.answer)
        return {k: sorted(v, key=lambda a: a.answered_at) for k, v in answers.items()}
