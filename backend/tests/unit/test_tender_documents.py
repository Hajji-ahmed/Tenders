"""Pièces d'un appel d'offres : enregistrement des URL, téléchargement résilient (un échec par
document, jamais d'exception), dépôt manuel validé ; job `download_tender_documents`."""

import httpx
import pytest
from sqlalchemy import select

from app.core import deps
from app.core.errors import ValidationError
from app.models import DownloadStatus, JobStatus, Tender, TenderDocument
from app.services.jobs import JobService
from app.services.tender_documents import TenderDocumentService

PDF = b"%PDF-1.4\n%fake tender document\n"
BIG = b"%PDF-1.4" + b"0" * (2 * 1024 * 1024)


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        match request.url.path:
            case "/dce.pdf":
                return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
            case "/reglement.pdf":  # type d'en-tête inutile : la signature binaire fait foi
                return httpx.Response(200, content=PDF, headers={"content-type": "application/octet-stream"})
            case "/missing.pdf":
                return httpx.Response(404, text="not found")
            case "/page.html":
                return httpx.Response(
                    200, text="<html>pas une pièce</html>", headers={"content-type": "text/html"}
                )
            case "/huge.pdf":
                return httpx.Response(200, content=BIG, headers={"content-type": "application/pdf"})
            case _:
                raise httpx.ConnectError("réseau injoignable")

    return httpx.MockTransport(handler)


@pytest.fixture
def http() -> httpx.Client:
    return httpx.Client(transport=_transport(), follow_redirects=True)


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="AO 27/2026", extra={"document_urls": ["https://portail.ma/dce.pdf"]})
    db.add(t)
    db.flush()
    return t


def test_register_urls_creates_pending_documents_once(db, storage, http, tender):
    svc = TenderDocumentService(db, storage, http)
    docs = svc.register_urls(
        tender, ["https://portail.ma/dce.pdf", "https://portail.ma/missing.pdf", "https://portail.ma/dce.pdf"]
    )
    assert [d.name for d in docs] == ["dce.pdf", "missing.pdf"]
    assert all(d.download_status == DownloadStatus.pending and d.tender_id == tender.id for d in docs)

    again = svc.register_urls(tender, ["https://portail.ma/dce.pdf", "https://portail.ma/reglement.pdf"])
    assert [d.name for d in again] == ["dce.pdf", "reglement.pdf"]
    assert again[0].id == docs[0].id  # idempotent sur l'URL
    assert db.scalar(select(TenderDocument).where(TenderDocument.name == "reglement.pdf")) is not None


def test_download_stores_the_file_and_records_failures_without_raising(
    db, storage, http, tender, monkeypatch
):
    monkeypatch.setattr(deps.get_settings(), "max_upload_mb", 1)
    svc = TenderDocumentService(db, storage, http)
    ok, sniffed, missing, html, huge, down = svc.register_urls(
        tender,
        [
            "https://portail.ma/dce.pdf",
            "https://portail.ma/reglement.pdf",
            "https://portail.ma/missing.pdf",
            "https://portail.ma/page.html",
            "https://portail.ma/huge.pdf",
            "https://hors-ligne.ma/x.pdf",
        ],
    )
    for doc in (ok, sniffed, missing, html, huge, down):
        svc.download(doc)

    assert ok.download_status == DownloadStatus.done and ok.error is None
    assert ok.mime_type == "application/pdf" and ok.size_bytes == len(PDF)
    assert ok.storage_key.startswith(f"tenders/{tender.id}/") and ok.storage_key.endswith(".pdf")
    assert storage.get(ok.storage_key) == PDF and len(ok.sha256) == 64

    assert sniffed.download_status == DownloadStatus.done and sniffed.mime_type == "application/pdf"
    assert missing.download_status == DownloadStatus.failed and "HTTP 404" in missing.error
    assert html.download_status == DownloadStatus.failed and "non pris en charge" in html.error
    assert huge.download_status == DownloadStatus.failed and "volumineux" in huge.error
    assert down.download_status == DownloadStatus.failed and "ConnectError" in down.error
    assert all(d.storage_key is None for d in (missing, html, huge, down))


def test_download_is_idempotent_once_done(db, storage, http, tender):
    svc = TenderDocumentService(db, storage, http)
    (doc,) = svc.register_urls(tender, ["https://portail.ma/dce.pdf"])
    svc.download(doc)
    key = doc.storage_key
    svc.download(doc)  # déjà téléchargé : rien ne bouge, pas de second appel réseau
    assert doc.storage_key == key and doc.download_status == DownloadStatus.done


def test_upload_manual_validates_and_stores(db, storage, http, tender):
    svc = TenderDocumentService(db, storage, http)
    doc = svc.upload_manual(tender, filename="CCTP.pdf", data=PDF, content_type="application/pdf")
    assert doc.download_status == DownloadStatus.done and doc.source_url is None
    assert doc.name == "CCTP.pdf" and doc.size_bytes == len(PDF) and storage.get(doc.storage_key) == PDF

    with pytest.raises(ValidationError, match="Type de fichier non autorisé"):
        svc.upload_manual(
            tender, filename="virus.exe", data=b"MZ\x90\x00", content_type="application/x-msdownload"
        )
    with pytest.raises(ValidationError):  # extension et type incohérents
        svc.upload_manual(tender, filename="dce.pdf", data=b"hello", content_type="text/plain")


def test_download_job_registers_extra_urls_and_survives_failures(
    db, storage, run_jobs_inline, tender, monkeypatch
):
    monkeypatch.setattr(deps, "_download_client_override", httpx.Client(transport=_transport()))
    tender.extra = {"document_urls": ["https://portail.ma/dce.pdf", "https://portail.ma/missing.pdf"]}
    db.flush()

    job = JobService.enqueue(
        db, "download_tender_documents", entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )
    db.refresh(job)

    assert job.status == JobStatus.done, job.error
    assert job.result == {"done": 1, "failed": 1}
    statuses = {d.name: d.download_status for d in tender.documents}
    assert statuses == {"dce.pdf": DownloadStatus.done, "missing.pdf": DownloadStatus.failed}
    assert job.progress == 100 and job.message and "missing.pdf" in job.message
