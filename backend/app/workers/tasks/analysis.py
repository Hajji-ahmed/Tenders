"""Job `analyze_tender` : la chaîne complète du dossier — télécharger les pièces manquantes (échecs
tolérés), indexer celles qui ne le sont pas (échecs tolérés), puis analyser. Progression 0 / 25 /
50 / 75 / 100. L'extraction des exigences (Phase 7) se branchera en fin de chaîne."""

from uuid import UUID

from app.core import deps
from app.models import DownloadStatus, ExtractionStatus, Tender
from app.services.analysis import AnalysisService
from app.services.indexing import IndexingService
from app.services.tender_documents import TenderDocumentService
from app.workers.tracking import set_progress, tracked_task


@tracked_task("analyze_tender")
def analyze_tender(db, job, *, tender_id: str) -> dict:
    tender = db.get(Tender, UUID(tender_id))
    if tender is None:
        raise ValueError(f"Opportunité introuvable : {tender_id}")

    set_progress(db, job, 0, "Téléchargement des pièces")
    documents = TenderDocumentService(db, deps.get_storage(), deps.get_download_client())
    documents.register_urls(tender, list((tender.extra or {}).get("document_urls", [])))
    downloaded = download_failed = 0
    for doc in [d for d in tender.documents if d.download_status != DownloadStatus.done and d.source_url]:
        documents.download(doc)
        if doc.download_status == DownloadStatus.done:
            downloaded += 1
        else:
            download_failed += 1
    db.commit()

    set_progress(db, job, 25, "Extraction et indexation des pièces")
    indexing = IndexingService(db, deps.get_storage(), deps.get_embeddings())
    indexed = index_failed = 0
    for doc in [
        d
        for d in tender.documents
        if d.download_status == DownloadStatus.done and d.extraction_status != ExtractionStatus.done
    ]:
        indexing.index("tender_document", doc)
        if indexing.last_error:
            index_failed += 1
        else:
            indexed += 1
        db.commit()

    set_progress(db, job, 50, "Analyse du dossier par l'IA")
    analysis = AnalysisService(db).analyze(tender)  # AppError « Aucun document exploitable » ⇒ job failed
    db.commit()

    set_progress(db, job, 75, "Extraction des exigences")  # branchée en Phase 7
    criteria, dates = len(tender.criteria), len(analysis.key_dates)
    summary = f"Analyse terminée : {criteria} critère{'s' if criteria > 1 else ''}, "
    summary += f"{dates} date{'s' if dates > 1 else ''} clé{'s' if dates > 1 else ''}"
    set_progress(db, job, 100, summary)
    return {
        "downloaded": downloaded,
        "download_failed": download_failed,
        "indexed": indexed,
        "index_failed": index_failed,
        "criteria": criteria,
    }
