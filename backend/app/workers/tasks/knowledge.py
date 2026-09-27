"""Jobs de la base de connaissances : `refresh_company_summary` régénère la présentation du profil
à partir des seuls faits vérifiables (`CompanyFacts`). L'indexation des documents d'entreprise passe
par le job `index_document` existant, enfilé au dépôt et à chaque nouvelle version."""

from datetime import UTC, datetime

from app.ai.prompts import company_summary
from app.core import deps
from app.services.company import CompanyService
from app.services.company_facts import company_facts
from app.workers.tracking import set_progress, tracked_task


@tracked_task("refresh_company_summary")
def refresh_company_summary(db, job) -> dict:
    facts = company_facts(db)
    set_progress(db, job, 20, "Rédaction du résumé du profil")
    # Une erreur du modèle fait échouer le job : le résumé précédent, lui, reste en place.
    text = (
        deps.get_llm()
        .text(system=company_summary.SYSTEM, user=company_summary.user_prompt(facts), tier="fast")
        .strip()
    )
    words = len(text.split())
    profile = CompanyService.get_profile(db)
    profile.ai_summary = text
    profile.ai_summary_updated_at = datetime.now(tz=UTC)
    db.flush()
    set_progress(db, job, 100, f"Résumé du profil mis à jour ({words} mots)")
    return {"words": words}
