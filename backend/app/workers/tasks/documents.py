"""Jobs sur les documents : `download_tender_documents` télécharge chaque pièce connue d'un appel
d'offres (URL découvertes par l'extracteur + pièces en attente) — un échec de document n'arrête
pas les autres ; `index_document` extrait, découpe et vectorise une pièce ou un document
d'entreprise — un échec d'extraction est rendu dans le résultat, le job reste `done`."""

from uuid import UUID

from app.core import deps
from app.models import CompanyDocument, DownloadStatus, Tender, TenderDocument
from app.services.indexing import IndexingService
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


@tracked_task("index_document")
def index_document(db, job, *, kind: str, document_id: str) -> dict:
    model = {"tender_document": TenderDocument, "company_document": CompanyDocument}.get(kind)
    if model is None:
        raise ValueError(f"Type de document inconnu : {kind}")
    doc = db.get(model, UUID(document_id))
    if doc is None:
        raise ValueError(f"Document introuvable : {document_id}")
    set_progress(db, job, 10, f"Extraction de {doc.name}")
    service = IndexingService(db, deps.get_storage(), deps.get_embeddings())
    chunks = service.index(kind, doc)  # type: ignore[arg-type]
    if service.last_error:
        set_progress(db, job, 100, f"{doc.name} : {service.last_error}")
        return {"chunks": 0, "error": service.last_error}
    set_progress(db, job, 100, f"{doc.name} : {chunks} morceaux indexés")
    return {"chunks": chunks, "pages": doc.page_count}
