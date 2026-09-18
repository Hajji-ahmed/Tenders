"""Jobs sur les pièces d'un appel d'offres : `download_tender_documents` télécharge chaque pièce
connue (URL découvertes par l'extracteur + pièces en attente) — un échec de document n'arrête pas
les autres. L'indexation (`index_document`) arrive en Task 6.3."""

from uuid import UUID

from app.core import deps
from app.models import DownloadStatus, Tender
from app.services.tender_documents import TenderDocumentService
from app.workers.tracking import set_progress, tracked_task


@tracked_task("download_tender_documents")
def download_tender_documents(db, job, *, tender_id: str) -> dict:
    tender = db.get(Tender, UUID(tender_id))
    if tender is None:
        raise ValueError(f"Opportunité introuvable : {tender_id}")
    service = TenderDocumentService(db, deps.get_storage(), deps.get_download_client())
    service.register_urls(tender, list((tender.extra or {}).get("document_urls", [])))
    pending = [d for d in tender.documents if d.download_status != DownloadStatus.done and d.source_url]

    done = failed = 0
    failures: list[str] = []
    for index, doc in enumerate(pending):
        set_progress(
            db, job, int(index * 100 / max(len(pending), 1)), f"Pièce {index + 1}/{len(pending)} : {doc.name}"
        )
        service.download(doc)
        if doc.download_status == DownloadStatus.done:
            done += 1
        else:
            failed += 1
            failures.append(doc.name)
        db.commit()  # chaque pièce est acquise indépendamment des suivantes
    summary = f"{done} pièce{'s' if done > 1 else ''} téléchargée{'s' if done > 1 else ''}"
    if failures:
        summary += f", {failed} en échec : {', '.join(failures)}"
    set_progress(db, job, 100, summary)
    return {"done": done, "failed": failed}
