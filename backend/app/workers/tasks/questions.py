"""Job `generate_questions` : une question ciblée par exigence que le moteur n'a pu trancher et qui
n'en a pas déjà une en cours (un appel LLM par exigence, repli générique en cas d'échec)."""

from uuid import UUID

from app.models import Tender
from app.services.questions import QuestionService
from app.workers.tracking import set_progress, tracked_task


def questions_message(open_count: int, created: int) -> str:
    if not open_count:
        return "Aucune question à traiter"
    s, n = ("s" if open_count > 1 else ""), ("s" if created > 1 else "")
    return f"{open_count} question{s} à traiter ({created} nouvelle{n})"


@tracked_task("generate_questions")
def generate_questions(db, job, *, tender_id: str) -> dict:
    tender = db.get(Tender, UUID(tender_id))
    if tender is None:
        raise ValueError(f"Opportunité introuvable : {tender_id}")
    set_progress(db, job, 10, f"Formulation des questions ({len(tender.requirements)} exigences)")
    created = QuestionService(db).generate(tender)
    open_count = QuestionService.open_count(tender)
    set_progress(db, job, 100, questions_message(open_count, len(created)))
    return {"created": len(created), "open": open_count}
