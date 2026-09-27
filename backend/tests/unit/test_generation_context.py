"""Contexte de génération (Task 9.3) : ce qu'une section reçoit pour être écrite — et rien d'autre.
Le `requires` du plan commande : une section qui ne demande pas les exigences ne les voit pas, et
ce qui n'est pas opposable (certification expirée, document inutilisable) n'y entre jamais."""

from datetime import date, timedelta

import pytest

from app.models import (
    Certification,
    DocumentChunk,
    Expert,
    Priority,
    Question,
    QuestionAnswer,
    QuestionStatus,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderAnalysis,
    TenderRequirement,
)
from app.models.company import CertificationCategory
from app.models.document import CompanyDocument, DocumentCategory, DocumentStatus
from app.services.generation_context import GenerationContext, build_context
from app.services.knowledge import KnowledgeBase

CHUNK_TEXT = "InnoSustain a rénové 4 200 points lumineux à Fès avec télégestion centralisée."


def _section(key="solution", title="Solution technique", requires=None, max_words=400) -> dict:
    return {
        "key": key,
        "title": title,
        "instructions": "Décrire la solution proposée.",
        "max_words": max_words,
        "requires": requires if requires is not None else ["company_facts", "tender_analysis", "kb"],
    }


@pytest.fixture
def dossier(db, company, fake_embeddings):
    """Profil enrichi (une certification valide, une expirée, deux documents) et un AO analysé."""
    today = date.today()
    company.experts.append(Expert(full_name="Nadia F.", role="Chef de projet énergie", years_experience=8))
    company.certifications.append(
        Certification(
            name="ISO 27001",
            category=CertificationCategory.securite,
            expires_at=today - timedelta(days=10),  # expirée : jamais opposable
        )
    )
    usable = CompanyDocument(
        company_id=company.id,
        name="Note-capacites.pdf",
        category=DocumentCategory.presentation,
        storage_key="company/note.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256="a" * 64,
    )
    archived = CompanyDocument(
        company_id=company.id,
        name="Vieille-plaquette.pdf",
        category=DocumentCategory.presentation,
        storage_key="company/vieille.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256="b" * 64,
        status=DocumentStatus.archived,
    )
    db.add_all([usable, archived])
    db.flush()
    for doc, text in ((usable, CHUNK_TEXT), (archived, CHUNK_TEXT + " (version 2019)")):
        db.add(
            DocumentChunk(
                owner_kind="company_document",
                owner_id=doc.id,
                company_document_id=doc.id,
                chunk_index=0,
                page=1,
                content=text,
                embedding=fake_embeddings.embed([text])[0],
                meta={"name": doc.name},
            )
        )

    tender = Tender(
        title="Salé : rénovation de l'éclairage public",
        organization="Commune de Salé",
        reference="27/2026",
        sector="Énergie",
    )
    tender.analysis = TenderAnalysis(
        object="Rénovation de l'éclairage public de la ville de Salé",
        organization="Commune de Salé",
        reference="27/2026",
        budget="18 000 000 MAD",
        duration="24 mois",
        location="Salé",
        key_dates=[{"label": "Remise des offres", "date": "2026-11-20", "source_page": 1}],
        deliverables=["Étude d'exécution", "Plateforme de télégestion"],
        requested_documents=[{"name": "Attestation fiscale", "mandatory": True, "source_page": 2}],
        eligibility_conditions=["Qualification éclairage public classe ≥ 2"],
        summary="Marché de rénovation LED avec télégestion.",
    )
    requirement = TenderRequirement(
        code="TECH-001",
        category=RequirementCategory.technique,
        description="Luminaires LED IP66 télégérés",
        is_mandatory=True,
        priority=Priority.CRITIQUE,
        status=RequirementStatus.A_VERIFIER,
        justification="Aucune technologie du profil ne correspond",
    )
    tender.requirements.append(requirement)
    db.add(tender)
    db.flush()
    question = Question(
        tender_id=tender.id,
        requirement_id=requirement.id,
        text="Disposez-vous de luminaires télégérés ?",
        priority=Priority.CRITIQUE,
        status=QuestionStatus.answered,
    )
    question.answer = QuestionAnswer(answer="Oui, gamme IP66 télégérée depuis 2024", answered_at=_dt())
    db.add(question)
    db.flush()
    return {"tender": tender, "kb": KnowledgeBase(db, fake_embeddings), "usable": usable}


def _dt():
    from datetime import UTC, datetime

    return datetime.now(tz=UTC)


def test_context_carries_only_verifiable_company_facts(db, dossier):
    context = build_context(db, dossier["kb"], dossier["tender"], _section())

    assert isinstance(context, GenerationContext)
    assert context.company.trade_name == "InnoSustain"
    names = [c.name for c in context.company.certifications]
    assert "ISO 14001" in names and "ISO 27001" not in names  # l'expirée reste dehors (RB-007)
    assert [e.full_name for e in context.company.experts] == ["Nadia F."]


def test_context_carries_the_tender_as_analysed(db, dossier):
    context = build_context(db, dossier["kb"], dossier["tender"], _section())

    assert context.tender["title"].startswith("Salé") and context.tender["reference"] == "27/2026"
    assert context.tender["object"].startswith("Rénovation") and context.tender["budget"] == "18 000 000 MAD"
    assert context.tender["deliverables"] == ["Étude d'exécution", "Plateforme de télégestion"]
    assert context.tender["key_dates"][0]["label"] == "Remise des offres"


def test_kb_extracts_come_only_from_usable_documents(db, dossier):
    context = build_context(db, dossier["kb"], dossier["tender"], _section())

    assert context.kb_hits and all(h.document_name == "Note-capacites.pdf" for h in context.kb_hits)
    assert "[S1] (Note-capacites.pdf p. 1)" in context.kb_context
    assert "version 2019" not in context.kb_context  # document archivé : pas de citation possible


def test_a_section_sees_only_what_it_asked_for(db, dossier):
    minimal = build_context(db, dossier["kb"], dossier["tender"], _section(requires=["tender_analysis"]))
    assert minimal.tender["object"]
    assert minimal.company.legal_name == "" and minimal.company.certifications == []
    assert minimal.requirements == [] and minimal.answers == [] and minimal.kb_context == ""

    full = build_context(
        db,
        dossier["kb"],
        dossier["tender"],
        _section(requires=["company_facts", "requirements", "answers"]),
    )
    assert [r["code"] for r in full.requirements] == ["TECH-001"]
    assert full.requirements[0]["status"] == "A_VERIFIER" and full.requirements[0]["is_mandatory"] is True
    assert full.answers[0]["question"].startswith("Disposez-vous")
    assert full.answers[0]["answer"].startswith("Oui, gamme IP66")
    assert full.kb_hits == []


def test_a_repeated_section_carries_its_subject(db, dossier):
    expert = dossier["tender"].requirements  # noqa: F841 — lisibilité : on prend l'expert du profil
    context = build_context(
        db,
        dossier["kb"],
        dossier["tender"],
        _section(key="profil", title="Profil", requires=["company_facts"]),
        repeat_item={"kind": "experts", "label": "Nadia F.", "data": {"full_name": "Nadia F."}},
    )
    assert context.subject == {"kind": "experts", "label": "Nadia F.", "data": {"full_name": "Nadia F."}}


def test_template_instructions_and_limit_travel_with_the_context(db, dossier):
    context = build_context(db, dossier["kb"], dossier["tender"], _section(max_words=250))
    assert context.template_instructions == "Décrire la solution proposée."
    assert context.max_words == 250 and context.section_title == "Solution technique"
