"""Job `generate_application_documents` : rédige les documents demandés du dossier, l'un après
l'autre. Un document en échec est marqué comme tel et n'arrête pas les suivants — puis le dossier
passe en relecture, car rien ne part sans validation humaine (RB-006)."""

from uuid import UUID

from app.core import deps
from app.models import AppDocStatus, Application
from app.services.applications import ApplicationService
from app.services.generation import GenerationService, Progress
from app.services.knowledge import KnowledgeBase
from app.workers.tracking import set_progress, tracked_task


@tracked_task("generate_application_documents")
def generate_application_documents(
    db, job, *, application_id: str, document_ids: list[str] | None = None
) -> dict:
    application = db.get(Application, UUID(application_id))
    if application is None:
        raise ValueError(f"Dossier de candidature introuvable : {application_id}")
    service = ApplicationService(db)
    wanted = None if document_ids is None else [UUID(d) for d in document_ids]
    documents = service.documents_to_generate(application, wanted)
    if not documents:
        raise ValueError("Aucun document à générer : ajoutez d'abord un modèle au dossier")

    generation = GenerationService(db, deps.get_llm(), KnowledgeBase(db, deps.get_embeddings()))
    done = failed = warnings = 0
    total = len(documents)

    def step(base: int) -> Progress:
        """Progression du document ramenée à sa part dans celle du dossier."""

        def report(percent: int, message: str) -> None:
            set_progress(db, job, min(base + percent // total, 99), message)

        return report

    for index, doc in enumerate(documents):
        base = int(index * 100 / total)
        set_progress(db, job, base, f"{doc.title} ({index + 1}/{total})")
        try:
            generation.generate_document(doc, on_progress=step(base))
            done += 1
            warnings += len(doc.warnings)
        except Exception as e:  # noqa: BLE001 — un document perdu n'emporte pas le dossier
            failed += 1
            doc.status = AppDocStatus.failed
            doc.error = f"{type(e).__name__}: {e}"[:2000]
        db.commit()  # chaque document est acquis indépendamment des suivants

    status = service.set_status_after_generation(application)
    summary = f"{done} document{'s' if done > 1 else ''} rédigé{'s' if done > 1 else ''}"
    if failed:
        summary += f", {failed} en échec"
    if warnings:
        summary += f" — {warnings} point{'s' if warnings > 1 else ''} à vérifier"
    set_progress(db, job, 100, summary)
    return {"generated": done, "failed": failed, "warnings": warnings, "status": str(status)}
