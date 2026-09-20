"""Analyse du dossier : `POST /tenders/{id}/analyze` enfile la chaîne télécharger → indexer →
analyser (202 + JobOut) ; `GET /tenders/{id}/analysis` rend l'analyse structurée et ses critères."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import Tender
from app.schemas.job import JobOut
from app.schemas.tender import CriterionOut, TenderAnalysisOut
from app.services.jobs import JobService

ANALYZE_JOB = "analyze_tender"

router = APIRouter(prefix="/tenders", tags=["analysis"], dependencies=[Depends(get_current_user)])


def _tender_or_404(db: Session, tender_id: UUID) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    return tender


@router.post("/{tender_id}/analyze", response_model=JobOut, status_code=202)
def launch_analysis(tender_id: UUID, db: Session = Depends(get_db)):
    tender = _tender_or_404(db, tender_id)
    return JobService.enqueue(
        db, ANALYZE_JOB, entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )


@router.get("/{tender_id}/analysis", response_model=TenderAnalysisOut)
def get_analysis(tender_id: UUID, db: Session = Depends(get_db)):
    tender = _tender_or_404(db, tender_id)
    if tender.analysis is None:
        raise NotFoundError("Dossier non analysé", code="analysis_missing")
    out = TenderAnalysisOut.model_validate(tender.analysis)
    out.criteria = [CriterionOut.model_validate(c) for c in tender.criteria]
    return out
