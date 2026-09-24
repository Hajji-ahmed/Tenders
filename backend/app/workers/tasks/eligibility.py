"""Job `evaluate_eligibility` : juge chaque exigence d'une fiche contre le profil de l'entreprise (les
réponses déjà données aux questions priment), résume (ratio, obligatoires non satisfaites — RB-003),
relance le score, puis formule les questions ciblées pour ce qui reste à trancher."""

from uuid import UUID

from app.models import Tender
from app.services.company import CompanyService
from app.services.eligibility import EligibilityEngine
from app.services.questions import QuestionService
from app.workers.tasks.questions import questions_message
from app.workers.tracking import set_progress, tracked_task


@tracked_task("evaluate_eligibility")
def evaluate_eligibility(db, job, *, tender_id: str) -> dict:
    tender = db.get(Tender, UUID(tender_id))
    if tender is None:
        raise ValueError(f"Opportunité introuvable : {tender_id}")
    set_progress(db, job, 10, f"Évaluation de {len(tender.requirements)} exigences")
    engine = EligibilityEngine(db, CompanyService.get_or_create(db))
    summary = engine.evaluate(tender, QuestionService.answers_by_requirement(tender))
    db.commit()

    set_progress(db, job, 60, "Formulation des questions")
    created = QuestionService(db).generate(tender)
    open_count = QuestionService.open_count(tender)

    unmet = len(summary.mandatory_unmet)
    message = f"Éligibilité : {round(summary.ratio * 100)} %"
    if unmet:
        s = "s" if unmet > 1 else ""
        message += f" — {unmet} exigence{s} obligatoire{s} non satisfaite{s}"
    if open_count:
        message += f" — {questions_message(open_count, len(created))}"
    set_progress(db, job, 100, message)
    return {**summary.model_dump(), "questions": open_count, "new_questions": len(created)}
