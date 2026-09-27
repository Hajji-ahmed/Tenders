"""Endpoints /templates : liste filtrée, création, lecture et modification d'un plan de sections.
Une section doit rester utilisable par la génération — clés uniques, sources connues."""

import uuid

import pytest
from sqlalchemy import select

from app.models import AuditLog, DocumentType, Template
from app.services.templates import seed_templates

URL = "/api/v1/templates"

SECTIONS = [
    {
        "key": "contexte",
        "title": "Contexte et enjeux",
        "instructions": "Rappeler le besoin de l'organisme et son contexte.",
        "max_words": 300,
        "requires": ["tender_analysis"],
    },
    {
        "key": "reponse",
        "title": "Notre réponse",
        "instructions": "Décrire la solution proposée, sans rien promettre qui ne soit au profil.",
        "max_words": 400,
        "requires": ["company_facts", "kb"],
    },
]


@pytest.fixture
def seeded(db) -> list[Template]:
    return seed_templates(db)


def test_list_returns_the_default_templates_and_filters_by_type(auth_client, seeded):
    body = auth_client.get(URL).json()
    assert body["total"] == len(seeded) and len(body["items"]) == len(seeded)
    first = body["items"][0]
    assert first["sections"] and first["section_count"] == len(first["sections"])

    body = auth_client.get(URL, params={"document_type": "cv"}).json()
    assert [t["document_type"] for t in body["items"]] == ["cv"]
    assert body["items"][0]["repeat_for"] == "experts"

    assert auth_client.get(URL, params={"document_type": "chanson"}).status_code == 422


def test_create_read_and_patch_a_template(auth_client, db, user):
    r = auth_client.post(
        URL,
        json={
            "name": "Offre technique — éclairage",
            "document_type": "offre_technique",
            "description": "Variante éclairage public",
            "sections": SECTIONS,
        },
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["is_default"] is False and created["version"] == 1 and created["language"] == "fr"
    assert [s["key"] for s in created["sections"]] == ["contexte", "reponse"]

    fetched = auth_client.get(f"{URL}/{created['id']}").json()
    assert fetched["name"] == "Offre technique — éclairage"

    r = auth_client.patch(
        f"{URL}/{created['id']}",
        json={"name": "Offre technique LED", "sections": SECTIONS[:1]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Offre technique LED" and r.json()["section_count"] == 1
    assert r.json()["version"] == 2  # le plan a changé : nouvelle version du modèle

    audit = db.scalars(select(AuditLog).where(AuditLog.entity_kind == "template")).all()
    assert {a.action for a in audit} == {"template.created", "template.updated"}
    assert all(a.user_id == user.id for a in audit)


def test_a_section_plan_must_stay_usable(auth_client, seeded):
    duplicate = [SECTIONS[0], {**SECTIONS[1], "key": "contexte"}]
    r = auth_client.post(
        URL, json={"name": "Doublon", "document_type": "methodologie", "sections": duplicate}
    )
    assert r.status_code == 422 and "unique" in r.json()["error"]["message"].lower()

    unknown = [{**SECTIONS[0], "requires": ["horoscope"]}]
    r = auth_client.post(
        URL, json={"name": "Source inconnue", "document_type": "methodologie", "sections": unknown}
    )
    assert r.status_code == 422

    r = auth_client.post(URL, json={"name": "Sans plan", "document_type": "methodologie", "sections": []})
    assert r.status_code == 422

    template = next(t for t in seeded if t.document_type == DocumentType.methodologie)
    assert auth_client.patch(f"{URL}/{template.id}", json={"sections": duplicate}).status_code == 422


def test_patching_only_metadata_keeps_the_version(auth_client, seeded):
    template = next(t for t in seeded if t.document_type == DocumentType.presentation)
    r = auth_client.patch(f"{URL}/{template.id}", json={"description": "Plaquette 2026"})
    assert r.status_code == 200 and r.json()["version"] == 1


def test_unknown_template_is_a_404(auth_client):
    assert auth_client.get(f"{URL}/{uuid.uuid4()}").status_code == 404
    assert auth_client.patch(f"{URL}/{uuid.uuid4()}", json={"name": "Inconnu"}).status_code == 404


def test_templates_require_auth(client):
    assert client.get(URL).status_code == 401
