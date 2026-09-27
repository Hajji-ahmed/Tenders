"""Recherche interne (Module 18) : une requête traverse les opportunités, les documents et le profil
(projets, experts, références, certifications) ; résultats groupés par nature, avec l'adresse de la
page où les ouvrir. En mode sémantique, les morceaux indexés et les fiches proches s'y ajoutent."""

from datetime import date, timedelta

import pytest

from app.models import Certification, DocumentChunk, Expert, Project, Reference, Tender, TenderDocument
from app.models.company import CertificationCategory
from app.models.document import CompanyDocument, DocumentCategory, DocumentStatus

URL = "/api/v1/search"


@pytest.fixture
def haystack(db, company, fake_embeddings):
    """Un projet cybersécurité, un expert, une référence, une certification, un document et deux AO."""
    today = date.today()
    company.projects.append(
        Project(
            title="Schéma directeur SI",
            client="Région Nord",
            sector="IT",
            description="Audit de cybersécurité et plan de remédiation.",
        )
    )
    company.experts.append(Expert(full_name="Karim B.", role="Ingénieur cybersécurité", years_experience=11))
    company.references.append(
        Reference(client_name="Office National X", sector="Énergie", description="Audit énergétique 2025")
    )
    company.certifications.append(
        Certification(
            name="ISO 27001",
            issuer="Bureau Veritas",
            category=CertificationCategory.securite,
            expires_at=today + timedelta(days=300),
        )
    )
    db.add(
        CompanyDocument(
            company_id=company.id,
            name="Politique de cybersécurité",
            category=DocumentCategory.administratif,
            description="Politique interne de sécurité des systèmes d'information",
            storage_key="company/psi.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="d" * 64,
        )
    )
    tenders = [
        Tender(
            title="Audit de cybersécurité du SI",
            organization="Commune de Salé",
            description="Audit technique et organisationnel.",
            embedding=fake_embeddings.embed(["Audit de cybersécurité du SI"])[0],
        ),
        Tender(title="Rénovation de l'éclairage public", organization="Commune de Salé"),
    ]
    db.add_all(tenders)
    db.flush()
    piece = TenderDocument(
        tender_id=tenders[1].id,
        name="RC-27-2026.pdf",
        storage_key="t/rc.pdf",
        mime_type="application/pdf",
    )
    db.add(piece)
    db.flush()
    db.add(
        DocumentChunk(
            owner_kind="tender_document",
            owner_id=piece.id,
            tender_id=tenders[1].id,
            chunk_index=0,
            page=2,
            content="Le titulaire assure la supervision et la cybersécurité de la plateforme de télégestion.",
            embedding=fake_embeddings.embed(
                ["Le titulaire assure la supervision et la cybersécurité de la plateforme de télégestion."]
            )[0],
        )
    )
    db.flush()
    return {"tenders": tenders, "piece": piece}


def _groups(body: dict) -> dict[str, list[dict]]:
    return {g["kind"]: g["items"] for g in body["groups"]}


def test_text_search_crosses_tenders_documents_and_profile(auth_client, haystack):
    body = auth_client.get(URL, params={"q": "cyber"}).json()

    groups = _groups(body)
    assert body["query"] == "cyber" and body["total"] == sum(len(v) for v in groups.values())
    assert [i["title"] for i in groups["projects"]] == ["Schéma directeur SI"]  # « cybersécurité » décrite
    assert groups["projects"][0]["url"] == f"/company?tab=projects&id={groups['projects'][0]['id']}"
    assert [i["title"] for i in groups["experts"]] == ["Karim B."]
    assert groups["experts"][0]["subtitle"] == "Ingénieur cybersécurité · 11 ans d'expérience"
    assert [i["title"] for i in groups["documents"]] == ["Politique de cybersécurité"]
    assert groups["documents"][0]["url"].endswith(f"?open={groups['documents'][0]['id']}")
    assert [i["title"] for i in groups["tenders"]] == ["Audit de cybersécurité du SI"]
    assert groups["tenders"][0]["url"] == f"/tenders/{haystack['tenders'][0].id}"
    assert "certifications" not in groups and "references" not in groups  # aucun résultat ⇒ pas de groupe


def test_search_can_be_limited_to_some_kinds(auth_client, haystack):
    body = auth_client.get(URL, params={"q": "cyber", "kinds": "tenders,experts"}).json()
    assert sorted(_groups(body)) == ["experts", "tenders"]

    assert auth_client.get(URL, params={"q": "cyber", "kinds": "dragons"}).status_code == 422


def test_profile_entities_are_found_by_their_own_words(auth_client, haystack):
    groups = _groups(auth_client.get(URL, params={"q": "énergétique"}).json())
    assert [i["title"] for i in groups["references"]] == ["Office National X"]

    groups = _groups(auth_client.get(URL, params={"q": "27001"}).json())
    assert [i["title"] for i in groups["certifications"]] == ["ISO 27001"]
    assert groups["certifications"][0]["subtitle"].startswith("Bureau Veritas")


def test_semantic_search_adds_documents_and_similar_tenders(auth_client, db, fake_embeddings, haystack):
    query = "Le titulaire assure la supervision et la cybersécurité de la plateforme de télégestion."

    plain = _groups(auth_client.get(URL, params={"q": query}).json())
    assert "tenders" not in plain  # aucun titre ne contient cette phrase

    body = auth_client.get(URL, params={"q": query, "semantic": "true"}).json()
    groups = _groups(body)
    piece = next(i for i in groups["documents"] if i["title"] == "RC-27-2026.pdf")
    assert piece["score"] > 0.99 and "p. 2" in (piece["subtitle"] or "")
    assert piece["url"] == f"/tenders/{haystack['tenders'][1].id}?tab=analysis"
    assert piece["excerpt"] and "télégestion" in piece["excerpt"]


def test_similar_tenders_are_found_by_their_embedding(auth_client, haystack):
    body = auth_client.get(
        URL, params={"q": "Audit de cybersécurité du SI", "semantic": "true", "kinds": "tenders"}
    ).json()
    items = _groups(body)["tenders"]
    assert items[0]["title"] == "Audit de cybersécurité du SI" and items[0]["score"] >= 0.99
    assert len(items) == 1  # la fiche n'est comptée qu'une fois (texte et sémantique fusionnés)


def test_distant_semantic_matches_are_dropped(auth_client, haystack):
    """Le plus proche n'est pas forcément proche : sous le plancher, on ne propose rien (constaté en
    réel — une question sur la télégestion remontait dix opportunités sans rapport, à 34 %)."""
    body = auth_client.get(URL, params={"q": "recette de tajine aux pruneaux", "semantic": "true"}).json()
    assert body["groups"] == [] and body["total"] == 0


def test_unusable_documents_are_flagged_and_never_quoted(auth_client, db, haystack):
    """RB-007 vaut pour ce qu'on cite, pas pour ce qu'on cherche : un document archivé reste trouvable
    (on veut pouvoir le rouvrir), mais son contenu n'est plus versé comme extrait."""
    doc = db.query(CompanyDocument).filter_by(name="Politique de cybersécurité").one()
    doc.status = DocumentStatus.archived
    db.flush()

    groups = _groups(auth_client.get(URL, params={"q": "cyber", "semantic": "true"}).json())
    found = next(i for i in groups["documents"] if i["title"] == "Politique de cybersécurité")
    assert "archivé" in found["subtitle"] and found["excerpt"] is None


def test_empty_or_short_query_returns_nothing(auth_client, haystack):
    assert auth_client.get(URL, params={"q": " "}).status_code == 422
    body = auth_client.get(URL, params={"q": "ab"}).json()
    assert body["groups"] == [] and body["total"] == 0


def test_search_requires_authentication(client):
    assert client.get(URL, params={"q": "cyber"}).status_code == 401
