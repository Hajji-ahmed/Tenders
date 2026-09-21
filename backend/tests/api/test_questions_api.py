"""Endpoints des questions : liste triée par priorité (filtre statut), génération (job), réponse
(ré-évalue l'exigence liée) et abandon."""

import uuid

import pytest

from app.models import (
    Priority,
    Question,
    QuestionStatus,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderRequirement,
)

URL = "/api/v1"


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="AO 27/2026", sector="Énergie")
    t.requirements.extend(
        [
            TenderRequirement(
                code="ADM-001",
                category=RequirementCategory.administrative,
                description="Attestation CNSS",
                is_mandatory=True,
                priority=Priority.IMPORTANTE,
                status=RequirementStatus.INFO_MANQUANTE,
            ),
            TenderRequirement(
                code="EXP-001",
                category=RequirementCategory.experience,
                description="Deux références similaires",
                is_mandatory=False,
                priority=Priority.FACULTATIVE,
                status=RequirementStatus.A_VERIFIER,
            ),
            TenderRequirement(
                code="METH-001",
                category=RequirementCategory.methodologie,
                description="Note méthodologique",
                is_mandatory=False,
                priority=Priority.IMPORTANTE,
                status=RequirementStatus.A_VERIFIER,
            ),
        ]
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db, tender) -> list[Question]:
    by_code = {r.code: r for r in tender.requirements}
    rows = [
        Question(
            tender_id=tender.id,
            requirement_id=by_code["EXP-001"].id,
            text="Disposez-vous de deux références similaires ?",
            priority=Priority.FACULTATIVE,
        ),
        Question(
            tender_id=tender.id,
            requirement_id=by_code["METH-001"].id,
            text="Qui rédige la note méthodologique ?",
            priority=Priority.IMPORTANTE,
            status=QuestionStatus.skipped,
        ),
        Question(
            tender_id=tender.id,
            requirement_id=by_code["ADM-001"].id,
            text="Avez-vous une attestation CNSS de moins de trois mois ?",
            priority=Priority.CRITIQUE,
        ),
    ]
    db.add_all(rows)
    db.flush()
    return rows


def test_list_questions_sorted_by_priority_with_status_filter(auth_client, tender, questions):
    body = auth_client.get(f"{URL}/tenders/{tender.id}/questions").json()
    assert [q["priority"] for q in body] == ["CRITIQUE", "IMPORTANTE", "FACULTATIVE"]
    first = body[0]
    assert first["requirement_code"] == "ADM-001" and first["requirement_status"] == "INFO_MANQUANTE"
    assert first["status"] == "open" and first["answer"] is None and first["is_mandatory"] is True

    open_only = auth_client.get(f"{URL}/tenders/{tender.id}/questions", params={"status": "open"}).json()
    assert [q["requirement_code"] for q in open_only] == ["ADM-001", "EXP-001"]
    assert auth_client.get(f"{URL}/tenders/{uuid.uuid4()}/questions").status_code == 404


def test_generate_questions_endpoint_runs_a_job(auth_client, db, run_jobs_inline, fake_llm, company, tender):
    r = auth_client.post(f"{URL}/tenders/{tender.id}/questions/generate")
    assert r.status_code == 202, r.text
    assert r.json()["type"] == "generate_questions" and r.json()["entity_id"] == str(tender.id)
    job = auth_client.get(f"{URL}/jobs/{r.json()['id']}").json()
    assert job["status"] == "done" and job["result"] == {"created": 3, "open": 3}

    body = auth_client.get(f"{URL}/tenders/{tender.id}/questions").json()
    assert [q["requirement_code"] for q in body] == ["ADM-001", "METH-001", "EXP-001"]
    assert body[0]["priority"] == "CRITIQUE" and body[0]["text"].endswith("?")
    assert auth_client.post(f"{URL}/tenders/{uuid.uuid4()}/questions/generate").status_code == 404


def test_answer_and_skip_endpoints(auth_client, db, company, tender, questions, fake_llm):
    critical = questions[2]
    r = auth_client.post(f"{URL}/questions/{critical.id}/answer", json={"answer": "Oui, du 3 septembre"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "answered" and body["answer"]["answer"] == "Oui, du 3 septembre"
    assert body["answer"]["answered_at"] and body["requirement_status"] == "CONFORME"
    assert auth_client.get(f"{URL}/tenders/{tender.id}/eligibility").json()["mandatory_unmet"] == []

    r = auth_client.post(f"{URL}/questions/{questions[0].id}/skip")
    assert r.status_code == 200 and r.json()["status"] == "skipped"
    assert r.json()["requirement_status"] == "A_VERIFIER"

    assert (
        auth_client.post(f"{URL}/questions/{critical.id}/answer", json={"answer": "   "}).status_code == 422
    )
    assert (
        auth_client.post(f"{URL}/questions/{uuid.uuid4()}/answer", json={"answer": "Oui"}).status_code == 404
    )
    assert auth_client.post(f"{URL}/questions/{uuid.uuid4()}/skip").status_code == 404


def test_questions_require_auth(client, tender):
    assert client.get(f"{URL}/tenders/{tender.id}/questions").status_code == 401
