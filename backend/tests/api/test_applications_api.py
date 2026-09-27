"""Dossier de candidature de bout en bout (Task 9.4) : ouverture après la décision GO, ajout de
documents depuis les modèles, rédaction par un job, lecture, export DOCX et téléchargement."""

import io
import uuid

import pytest
from docx import Document as read_docx
from sqlalchemy import select

from app.ai.outputs import SectionOutput
from app.models import Application, AuditLog, DocumentType, Tender, TenderStatus
from app.services.templates import seed_templates

URL = "/api/v1"


@pytest.fixture
def templates(db):
    return {t.document_type: t for t in seed_templates(db)}


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="Salé : rénovation de l'éclairage public", organization="Commune de Salé")
    t.status = TenderStatus.GO
    db.add(t)
    db.flush()
    return t


def _open(client, tender) -> dict:
    r = client.post(f"{URL}/tenders/{tender.id}/application")
    assert r.status_code == 201, r.text
    return r.json()


def _add(client, application_id: str, template) -> list[dict]:
    r = client.post(
        f"{URL}/applications/{application_id}/documents", json={"template_ids": [str(template.id)]}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_opening_a_file_requires_a_go_decision(auth_client, db, tender):
    tender.status = TenderStatus.NOUVEAU
    db.flush()
    r = auth_client.post(f"{URL}/tenders/{tender.id}/application")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_transition"

    tender.status = TenderStatus.GO
    db.flush()
    body = _open(auth_client, tender)
    assert body["status"] == "draft" and body["documents"] == []
    assert body["tender_title"].startswith("Salé")
    db.refresh(tender)
    assert tender.status == TenderStatus.PREPARATION  # la fiche suit le dossier

    again = _open(auth_client, tender)  # idempotent : on entre dans le dossier, on ne le redouble pas
    assert again["id"] == body["id"]
    assert db.scalar(select(Application).where(Application.tender_id == tender.id)) is not None


def test_documents_are_added_from_templates_and_never_doubled(auth_client, db, tender, templates):
    application = _open(auth_client, tender)
    letter = templates[DocumentType.lettre_candidature]

    created = _add(auth_client, application["id"], letter)
    assert len(created) == 1
    doc = created[0]
    assert doc["title"] == f"{letter.name} — {tender.title[:60]}"
    assert doc["status"] == "pending" and doc["current_version"] == 0 and doc["sections"] == []

    assert _add(auth_client, application["id"], letter) == []  # déjà présent
    body = auth_client.get(f"{URL}/applications/{application['id']}").json()
    assert len(body["documents"]) == 1

    r = auth_client.post(
        f"{URL}/applications/{application['id']}/documents", json={"template_ids": [str(uuid.uuid4())]}
    )
    assert r.status_code == 404


def test_full_flow_generates_a_draft_with_sections(
    auth_client, db, run_jobs_inline, fake_embeddings, monkeypatch, tender, templates, company
):
    from app.ai.llm import FakeLLM
    from app.core import deps

    letter = templates[DocumentType.lettre_candidature]
    application = _open(auth_client, tender)
    document = _add(auth_client, application["id"], letter)[0]
    sections = len(letter.sections)
    monkeypatch.setattr(
        deps,
        "_llm_override",
        FakeLLM(
            [
                SectionOutput(content_md=f"## Partie {i}", used_sources=[], missing_info=[])
                for i in range(sections)
            ]
        ),
    )

    r = auth_client.post(f"{URL}/applications/{application['id']}/generate")
    assert r.status_code == 202, r.text
    job = auth_client.get(f"{URL}/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert job["result"]["generated"] == 1 and job["result"]["failed"] == 0

    body = auth_client.get(f"{URL}/applications/{application['id']}").json()
    assert body["status"] == "review"  # rien ne part sans relecture (RB-006)
    doc = body["documents"][0]
    assert doc["status"] == "draft" and doc["current_version"] == 1
    assert [s["key"] for s in doc["sections"]] == [s["key"] for s in letter.sections]
    assert doc["sections"][0]["content_md"].startswith("## Partie")
    assert doc["has_export"] is False

    detail = auth_client.get(f"{URL}/applications/{application['id']}/documents/{document['id']}").json()
    assert detail["id"] == document["id"] and len(detail["sections"]) == sections
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "application_document.generated")).all()
    assert len(audit) == 1


def test_a_document_that_fails_does_not_lose_the_file(
    auth_client, db, run_jobs_inline, fake_embeddings, monkeypatch, tender, templates, company
):
    from app.core import deps

    class Broken:
        def structured(self, **kwargs):
            raise RuntimeError("quota dépassé")

        def text(self, **kwargs):
            raise RuntimeError("quota dépassé")

    monkeypatch.setattr(deps, "_llm_override", Broken())
    application = _open(auth_client, tender)
    _add(auth_client, application["id"], templates[DocumentType.declaration])

    job = auth_client.post(f"{URL}/applications/{application['id']}/generate").json()
    job = auth_client.get(f"{URL}/jobs/{job['id']}").json()

    assert job["status"] == "done"  # le job aboutit : c'est le document qui a échoué, pas le traitement
    doc = auth_client.get(f"{URL}/applications/{application['id']}").json()["documents"][0]
    assert doc["status"] == "draft" and doc["sections"]  # les sections portent leur échec en clair
    assert doc["sections"][0]["content_md"].startswith("[Génération échouée")


def test_export_produces_a_docx_and_download_serves_it(
    auth_client, db, storage, run_jobs_inline, fake_embeddings, monkeypatch, tender, templates, company
):
    from app.ai.llm import FakeLLM
    from app.core import deps

    letter = templates[DocumentType.lettre_candidature]
    application = _open(auth_client, tender)
    document = _add(auth_client, application["id"], letter)[0]
    monkeypatch.setattr(
        deps,
        "_llm_override",
        FakeLLM(
            [
                SectionOutput(content_md="Texte de la partie.", used_sources=[], missing_info=[])
                for _ in letter.sections
            ]
        ),
    )
    auth_client.post(f"{URL}/applications/{application['id']}/generate")

    r = auth_client.post(f"{URL}/applications/{application['id']}/documents/{document['id']}/export")
    assert r.status_code == 200, r.text
    assert r.json()["has_export"] is True

    r = auth_client.get(f"{URL}/applications/{application['id']}/documents/{document['id']}/download")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    docx = read_docx(io.BytesIO(r.content))
    headings = [p.text for p in docx.paragraphs if p.style.name == "Heading 1"]
    assert headings == [s["title"] for s in letter.sections]


def test_exporting_before_generation_is_refused(auth_client, db, tender, templates):
    application = _open(auth_client, tender)
    document = _add(auth_client, application["id"], templates[DocumentType.equipe])[0]
    r = auth_client.post(f"{URL}/applications/{application['id']}/documents/{document['id']}/export")
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_generated"


def test_unknown_ids_are_404(auth_client, db, tender, templates):
    application = _open(auth_client, tender)
    assert auth_client.get(f"{URL}/applications/{uuid.uuid4()}").status_code == 404
    assert (
        auth_client.get(f"{URL}/applications/{application['id']}/documents/{uuid.uuid4()}").status_code == 404
    )
    assert auth_client.post(f"{URL}/tenders/{uuid.uuid4()}/application").status_code == 404
    r = auth_client.post(
        f"{URL}/applications/{application['id']}/generate", json={"document_ids": [str(uuid.uuid4())]}
    )
    assert r.status_code == 404


def test_applications_require_auth(client, tender):
    assert client.post(f"{URL}/tenders/{tender.id}/application").status_code == 401
    assert client.get(f"{URL}/applications/{uuid.uuid4()}").status_code == 401
