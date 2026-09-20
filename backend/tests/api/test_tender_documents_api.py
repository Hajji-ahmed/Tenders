"""Endpoints /tenders/{id}/documents : liste, dépôt manuel, récupération par job, téléchargement."""

import uuid

import httpx
import pytest

from app.core import deps
from app.models import Tender, TenderDocument

URL = "/api/v1/tenders"
PDF = b"%PDF-1.4\n%fake\n"


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(
        title="AO 27/2026",
        extra={"document_urls": ["https://portail.ma/dce.pdf", "https://portail.ma/nope.pdf"]},
    )
    t.documents.append(TenderDocument(name="dce.pdf", source_url="https://portail.ma/dce.pdf"))
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def mock_http(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dce.pdf":
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    monkeypatch.setattr(
        deps, "_download_client_override", httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_list_documents_of_a_tender(auth_client, tender):
    body = auth_client.get(f"{URL}/{tender.id}/documents").json()
    assert [d["name"] for d in body] == ["dce.pdf"]
    assert body[0]["download_status"] == "pending" and body[0]["tender_id"] == str(tender.id)
    assert auth_client.get(f"{URL}/{uuid.uuid4()}/documents").status_code == 404


def test_upload_manual_document(auth_client, tender):
    r = auth_client.post(f"{URL}/{tender.id}/documents", files={"file": ("CCTP.pdf", PDF, "application/pdf")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "CCTP.pdf" and body["download_status"] == "done" and body["size_bytes"] == len(PDF)

    bad = auth_client.post(
        f"{URL}/{tender.id}/documents", files={"file": ("virus.exe", b"MZ", "application/x-msdownload")}
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unsupported_file_type"

    names = [d["name"] for d in auth_client.get(f"{URL}/{tender.id}/documents").json()]
    assert sorted(names) == ["CCTP.pdf", "dce.pdf"]  # même `now()` de transaction : tri secondaire par nom


def test_fetch_enqueues_download_job_and_download_serves_the_file(
    auth_client, db, run_jobs_inline, storage, mock_http, tender
):
    r = auth_client.post(f"{URL}/{tender.id}/documents/fetch")
    assert r.status_code == 202, r.text
    assert r.json()["type"] == "download_tender_documents" and r.json()["entity_id"] == str(tender.id)
    job = auth_client.get(f"/api/v1/jobs/{r.json()['id']}").json()
    assert job["status"] == "done" and job["result"] == {"done": 1, "failed": 1}

    docs = {d["name"]: d for d in auth_client.get(f"{URL}/{tender.id}/documents").json()}
    assert docs["dce.pdf"]["download_status"] == "done" and docs["nope.pdf"]["download_status"] == "failed"
    assert "HTTP 404" in docs["nope.pdf"]["error"]

    dl = auth_client.get(f"{URL}/{tender.id}/documents/{docs['dce.pdf']['id']}/download")
    assert dl.status_code == 200 and dl.content == PDF and dl.headers["content-type"] == "application/pdf"
    assert 'filename="dce.pdf"' in dl.headers["content-disposition"]

    not_ready = auth_client.get(f"{URL}/{tender.id}/documents/{docs['nope.pdf']['id']}/download")
    assert not_ready.status_code == 404 and not_ready.json()["error"]["code"] == "not_downloaded"


def test_tender_documents_require_auth(client, tender):
    assert client.get(f"{URL}/{tender.id}/documents").status_code == 401
    assert client.post(f"{URL}/{tender.id}/documents/fetch").status_code == 401
