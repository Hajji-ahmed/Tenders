"""Job `analyze_tender` : télécharger les pièces manquantes → indexer → analyser, avec progression ;
endpoints POST /tenders/{id}/analyze et GET /tenders/{id}/analysis."""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.ai.outputs import (
    CriterionOut,
    DatedItem,
    RequirementOutput,
    RequirementsOutput,
    TenderAnalysisOutput,
)
from app.core import deps
from app.models import (
    DocumentChunk,
    DownloadStatus,
    ExtractionStatus,
    JobStatus,
    Priority,
    RequirementCategory,
    Tender,
)
from app.services.jobs import JobService

URL = "/api/v1/tenders"


def _output() -> TenderAnalysisOutput:
    return TenderAnalysisOutput(
        object="Attestation fiscale — objet fictif pour le test",
        organization="InnoSustain",
        reference=None,
        budget=None,
        duration=None,
        location="Casablanca",
        key_dates=[DatedItem(label="Date limite de remise des offres", date=None, source_page=1)],
        deliverables=["Rapport"],
        evaluation_criteria=[
            CriterionOut(name="Prix", weight=50, description=None, source_page=1),
            CriterionOut(name="Technique", weight=30, description=None, source_page=1),
            CriterionOut(name="Délai", weight=20, description=None, source_page=1),
        ],
        requested_documents=[],
        eligibility_conditions=[],
        summary="Résumé de test.",
    )


@pytest.fixture
def real_pdf(fixtures_dir) -> bytes:
    return (fixtures_dir / "sample.pdf").read_bytes()


@pytest.fixture
def chain_env(monkeypatch, real_pdf):
    """Client HTTP simulé (une pièce lisible, une 404), LLM scripté, embeddings factices."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dce.pdf":
            return httpx.Response(200, content=real_pdf, headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    monkeypatch.setattr(
        deps, "_download_client_override", httpx.Client(transport=httpx.MockTransport(handler))
    )
    requirements = RequirementsOutput(
        requirements=[
            RequirementOutput(
                category=RequirementCategory.administrative,
                description="Attestation fiscale en cours de validité",
                is_mandatory=True,
                evidence_required="Attestation fiscale",
                priority=Priority.CRITIQUE,
                source_document="dce.pdf",
                source_page=1,
                source_excerpt=None,
            )
        ]
    )
    llm = FakeLLM([_output(), requirements])  # analyse du dossier, puis exigences de l'unique pièce lisible
    monkeypatch.setattr(deps, "_llm_override", llm)
    return llm


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(
        title="AO test analyse",
        extra={"document_urls": ["https://portail.ma/dce.pdf", "https://portail.ma/absent.pdf"]},
    )
    db.add(t)
    db.flush()
    return t


def test_analyze_job_chains_download_index_and_analysis(
    db, storage, run_jobs_inline, fake_embeddings, chain_env, tender
):
    job = JobService.enqueue(
        db, "analyze_tender", entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )
    db.refresh(job)

    assert job.status == JobStatus.done, job.error
    assert job.result == {
        "downloaded": 1,
        "download_failed": 1,
        "indexed": 1,
        "index_failed": 0,
        "criteria": 3,
        "requirements": 1,
    }
    assert job.progress == 100 and "Analyse terminée" in (job.message or "") and "1 exigence" in job.message
    assert [r.code for r in tender.requirements] == ["ADM-001"]
    assert tender.requirements[0].source_document_id == next(
        d.id for d in tender.documents if d.name == "dce.pdf"
    )
    docs = {d.name: d for d in tender.documents}
    assert (
        docs["dce.pdf"].download_status == DownloadStatus.done
        and docs["dce.pdf"].extraction_status == ExtractionStatus.done
    )
    assert docs["absent.pdf"].download_status == DownloadStatus.failed
    assert db.scalar(select(DocumentChunk).where(DocumentChunk.tender_id == tender.id)) is not None
    assert tender.analysis is not None and tender.summary == "Résumé de test." and len(tender.criteria) == 3
    assert "=== dce.pdf — page 1 ===" in chain_env.calls[0]["user"]


def test_analyze_job_fails_readably_without_usable_document(
    db, storage, run_jobs_inline, fake_embeddings, monkeypatch
):
    monkeypatch.setattr(deps, "_llm_override", FakeLLM())
    t = Tender(title="Sans pièces")
    db.add(t)
    db.flush()
    job = JobService.enqueue(db, "analyze_tender", entity_kind="tender", entity_id=t.id, tender_id=str(t.id))
    db.refresh(job)
    assert job.status == JobStatus.failed and "Aucun document exploitable" in (job.error or "")


def test_analysis_endpoints(auth_client, db, storage, run_jobs_inline, fake_embeddings, chain_env, tender):
    assert auth_client.get(f"{URL}/{tender.id}/analysis").status_code == 404

    r = auth_client.post(f"{URL}/{tender.id}/analyze")
    assert r.status_code == 202, r.text
    assert r.json()["type"] == "analyze_tender" and r.json()["entity_id"] == str(tender.id)

    body = auth_client.get(f"{URL}/{tender.id}/analysis").json()
    assert body["object"].startswith("Attestation fiscale") and body["summary"] == "Résumé de test."
    assert body["key_dates"][0]["label"] == "Date limite de remise des offres"
    assert [c["name"] for c in body["criteria"]] == ["Prix", "Technique", "Délai"]
    assert body["criteria"][0]["weight"] == 50 and body["criteria"][0]["source_page"] == 1
    assert body["analyzed_at"] and body["prompt_version"] == "v1"

    assert auth_client.post(f"{URL}/{uuid.uuid4()}/analyze").status_code == 404
