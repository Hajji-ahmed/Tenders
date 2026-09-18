"""Qualification d'une opportunité : score (calcul à la demande, lecture), décision GO / NO-GO,
changement de statut, historique et vue kanban. Monté AVANT `tenders.router` : `/tenders/kanban`
serait sinon capturé par `/tenders/{tender_id}`."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import Tender, User
from app.repositories import tenders as tenders_repo
from app.schemas.job import JobOut
from app.schemas.tender import (
    DecisionIn,
    KanbanColumnOut,
    KanbanOut,
    StatusHistoryOut,
    StatusIn,
    TenderOut,
    TenderScoreOut,
)
from app.services import tender_status
from app.services.jobs import JobService

SCORE_JOB = "calculate_match_score"

router = APIRouter(prefix="/tenders", tags=["scoring"])


def _tender_or_404(db: Session, tender_id: UUID) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    return tender


@router.get("/kanban", response_model=KanbanOut)
def get_kanban(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    columns = tenders_repo.kanban(db)
    return KanbanOut(
        columns=[
            KanbanColumnOut(status=status, items=[TenderOut.model_validate(t) for t in items])
            for status, items in columns.items()
        ]
    )


@router.post("/{tender_id}/score", response_model=JobOut, status_code=202)
def launch_scoring(tender_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    tender = _tender_or_404(db, tender_id)
    return JobService.enqueue(
        db, SCORE_JOB, entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )


@router.get("/{tender_id}/score", response_model=TenderScoreOut)
def get_score(tender_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    tender = _tender_or_404(db, tender_id)
    if tender.score is None:
        raise NotFoundError("Score non calculé", code="score_missing")
    return tender.score


@router.post("/{tender_id}/decision", response_model=TenderOut)
def post_decision(
    tender_id: UUID,
    body: DecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tender = _tender_or_404(db, tender_id)
    tender_status.decide(db, tender, body.decision, reason=body.reason, user=user)
    return TenderOut.model_validate(tender)


@router.post("/{tender_id}/status", response_model=TenderOut)
def post_status(
    tender_id: UUID,
    body: StatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tender = _tender_or_404(db, tender_id)
    tender_status.transition(db, tender, body.status, comment=body.comment, user=user)
    return TenderOut.model_validate(tender)


@router.get("/{tender_id}/history", response_model=list[StatusHistoryOut])
def get_history(tender_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _tender_or_404(db, tender_id)
    return tenders_repo.list_status_history(db, tender_id)
