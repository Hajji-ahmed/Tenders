"""Job `evaluate_eligibility` : juge chaque exigence d'une fiche contre le profil de l'entreprise,
résume (ratio, obligatoires non satisfaites — RB-003) et relance le score. Les questions ciblées
(7.3) seront générées à la suite."""

from uuid import UUID

from app.models import Tender
from app.services.company import CompanyService
from app.services.eligibility import EligibilityEngine
from app.workers.tracking import set_progress, tracked_task


@tracked_task("evaluate_eligibility")
def evaluate_eligibility(db, job, *, tender_id: str) -> dict:
    tender = db.get(Tender, UUID(tender_id))
    if tender is None:
        raise ValueError(f"Opportunité introuvable : {tender_id}")
    set_progress(db, job, 10, f"Évaluation de {len(tender.requirements)} exigences")
    summary = EligibilityEngine(db, CompanyService.get_or_create(db)).evaluate(tender)
    unmet = len(summary.mandatory_unmet)
    message = f"Éligibilité : {round(summary.ratio * 100)} %"
    if unmet:
        s = "s" if unmet > 1 else ""
        message += f" — {unmet} exigence{s} obligatoire{s} non satisfaite{s}"
    set_progress(db, job, 100, message)
    return summary.model_dump()
