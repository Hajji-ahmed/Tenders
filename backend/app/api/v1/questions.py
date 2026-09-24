"""Questions ciblées d'un dossier : liste triée CRITIQUE > IMPORTANTE > FACULTATIVE (filtre statut),
génération (job `generate_questions`), réponse (ré-évalue l'exigence liée, résumé et score) et abandon."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import Question, QuestionStatus, Tender, TenderRequirement, User
from app.schemas.job import JobOut
from app.schemas.question import QuestionAnswerIn, QuestionOut
from app.services.jobs import JobService
from app.services.questions import PRIORITY_RANK, QuestionService

QUESTIONS_JOB = "generate_questions"

router = APIRouter(tags=["questions"], dependencies=[Depends(get_current_user)])


def _load(db: Session, question_id: UUID) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise NotFoundError("Question introuvable")
    return question


@router.get("/tenders/{tender_id}/questions", response_model=list[QuestionOut])
def list_questions(tender_id: UUID, status: QuestionStatus | None = None, db: Session = Depends(get_db)):
    if db.get(Tender, tender_id) is None:
        raise NotFoundError("Opportunité introuvable")
    rank = case({p.value: r for p, r in PRIORITY_RANK.items()}, value=Question.priority, else_=9)
    stmt = (  # à priorité égale, l'ordre des codes (ADM-001, ADM-002…) : `created_at` est le même
        select(Question)  # pour toutes les questions d'une génération (now() par transaction)
        .join(Question.requirement)
        .where(Question.tender_id == tender_id)
        .options(contains_eager(Question.requirement), selectinload(Question.answer))
        .order_by(rank, TenderRequirement.code, Question.created_at)
    )
    if status is not None:
        stmt = stmt.where(Question.status == status)
    return list(db.scalars(stmt))


@router.post("/tenders/{tender_id}/questions/generate", response_model=JobOut, status_code=202)
def launch_generation(tender_id: UUID, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    return JobService.enqueue(
        db, QUESTIONS_JOB, entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )


@router.post("/questions/{question_id}/answer", response_model=QuestionOut)
def answer_question(
    question_id: UUID,
    body: QuestionAnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    question = _load(db, question_id)
    QuestionService(db).answer(question, body.answer, user_id=user.id)
    return question


@router.post("/questions/{question_id}/skip", response_model=QuestionOut)
def skip_question(question_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return QuestionService(db).skip(_load(db, question_id), user_id=user.id)
