"""Job `calculate_match_score` : calcule (ou recalcule) le score d'une opportunité — règles +
justification IA — et le persiste. Enfilé automatiquement par la recherche pour chaque fiche créée
ou fusionnée, et à la demande depuis `POST /tenders/{id}/score`."""

from uuid import UUID

from app.models import Tender
from app.services.score_service import ScoreService
from app.workers.tracking import set_progress, tracked_task


@tracked_task("calculate_match_score")
def calculate_match_score(db, job, *, tender_id: str) -> dict:
    tender = db.get(Tender, UUID(tender_id))
    if tender is None:
        raise ValueError(f"Opportunité introuvable : {tender_id}")
    set_progress(db, job, 10, "Calcul du score")
    score = ScoreService(db).score_tender(tender)
    return {
        "tender_id": str(tender.id),
        "total": float(score.total),
        "adjustment": score.ai_adjustment,
        "status": str(tender.status),
    }
