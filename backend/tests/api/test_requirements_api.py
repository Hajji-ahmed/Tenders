"""Endpoints des exigences : liste filtrée d'une fiche, mise à jour manuelle (statut, justification,
obligatoire, priorité) auditée et marquée comme saisie à la main."""

import uuid

import pytest
from sqlalchemy import select

from app.models import AuditLog, Priority, RequirementCategory, RequirementStatus, Tender, TenderRequirement

URL = "/api/v1"


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="AO 27/2026")
    t.requirements.extend(
        [
            TenderRequirement(
                code="TECH-001",
                category=RequirementCategory.technique,
                description="Luminaires LED IP66",
                is_mandatory=True,
                priority=Priority.CRITIQUE,
            ),
            TenderRequirement(
                code="ADM-001",
                category=RequirementCategory.administrative,
                description="Attestation fiscale",
                is_mandatory=True,
                priority=Priority.IMPORTANTE,
                status=RequirementStatus.CONFORME,
            ),
            TenderRequirement(
                code="EXP-001",
                category=RequirementCategory.experience,
                description="Deux références",
                is_mandatory=False,
                priority=Priority.FACULTATIVE,
                status=RequirementStatus.INFO_MANQUANTE,
            ),
        ]
    )
    db.add(t)
    db.flush()
    return t


def test_list_requirements_with_filters(auth_client, tender):
    body = auth_client.get(f"{URL}/tenders/{tender.id}/requirements").json()
    assert [r["code"] for r in body] == ["ADM-001", "EXP-001", "TECH-001"]  # ordre alphabétique des codes
    assert (
        body[2]["category"] == "technique"
        and body[2]["status"] == "A_VERIFIER"
        and body[2]["manual_status"] is False
    )

    assert [
        r["code"]
        for r in auth_client.get(
            f"{URL}/tenders/{tender.id}/requirements", params={"status": "CONFORME"}
        ).json()
    ] == ["ADM-001"]
    assert [
        r["code"]
        for r in auth_client.get(
            f"{URL}/tenders/{tender.id}/requirements", params={"category": "experience"}
        ).json()
    ] == ["EXP-001"]
    assert [
        r["code"]
        for r in auth_client.get(
            f"{URL}/tenders/{tender.id}/requirements", params={"mandatory": "true"}
        ).json()
    ] == ["ADM-001", "TECH-001"]
    assert auth_client.get(f"{URL}/tenders/{uuid.uuid4()}/requirements").status_code == 404


def test_patch_requirement_marks_manual_status_and_audits(auth_client, db, tender, user):
    req = next(r for r in tender.requirements if r.code == "TECH-001")
    r = auth_client.patch(
        f"{URL}/requirements/{req.id}",
        json={"status": "CONFORME", "justification": "Gamme IP66 au catalogue"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONFORME" and r.json()["manual_status"] is True
    assert r.json()["justification"] == "Gamme IP66 au catalogue"

    r = auth_client.patch(
        f"{URL}/requirements/{req.id}", json={"is_mandatory": False, "priority": "FACULTATIVE"}
    )
    assert r.json()["is_mandatory"] is False and r.json()["priority"] == "FACULTATIVE"

    audit = db.scalars(select(AuditLog).where(AuditLog.action == "requirement.updated")).all()
    assert len(audit) == 2 and audit[0].user_id == user.id and audit[0].payload["code"] == "TECH-001"
    assert sorted(audit[0].payload["fields"]) == ["justification", "status"]

    assert auth_client.patch(f"{URL}/requirements/{req.id}", json={"status": "PEUT-ETRE"}).status_code == 422
    assert (
        auth_client.patch(f"{URL}/requirements/{uuid.uuid4()}", json={"status": "CONFORME"}).status_code
        == 404
    )


def test_requirements_require_auth(client, tender):
    assert client.get(f"{URL}/tenders/{tender.id}/requirements").status_code == 401
