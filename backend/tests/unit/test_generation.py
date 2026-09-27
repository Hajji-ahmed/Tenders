"""Génération d'un document de candidature (Task 9.3) : une section par entrée du plan, avec les
sources citées et ce qui a manqué ; une section perdue n'emporte pas le document ; les
avertissements du garde anti-invention restent attachés au document (RB-005)."""

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.ai.outputs import SectionOutput
from app.models import (
    AppDocStatus,
    Application,
    ApplicationDocument,
    ApplicationSection,
    AuditLog,
    DocumentChunk,
    DocumentType,
    SectionStatus,
    Template,
    Tender,
    TenderAnalysis,
)
from app.models.document import CompanyDocument, DocumentCategory
from app.services.generation import FAILED_PREFIX, GenerationService
from app.services.knowledge import KnowledgeBase

CHUNK = "InnoSustain a rénové 4 200 points lumineux à Fès, avec télégestion centralisée."


@pytest.fixture
def template(db) -> Template:
    t = Template(
        name="Offre technique",
        document_type=DocumentType.offre_technique,
        sections=[
            {
                "key": "contexte",
                "title": "Contexte et enjeux",
                "instructions": "Restituer le contexte.",
                "max_words": 200,
                "requires": ["tender_analysis"],
            },
            {
                "key": "solution",
                "title": "Solution technique",
                "instructions": "Décrire la solution.",
                "max_words": 300,
                "requires": ["company_facts", "kb"],
            },
            {
                "key": "livrables",
                "title": "Livrables",
                "instructions": "Lister les livrables.",
                "max_words": 150,
                "requires": ["tender_analysis"],
            },
        ],
        is_default=True,
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def document(db, company, fake_embeddings, template) -> ApplicationDocument:
    doc = CompanyDocument(
        company_id=company.id,
        name="Note-capacites.pdf",
        category=DocumentCategory.presentation,
        storage_key="company/note.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256="a" * 64,
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentChunk(
            owner_kind="company_document",
            owner_id=doc.id,
            company_document_id=doc.id,
            chunk_index=0,
            page=1,
            content=CHUNK,
            embedding=fake_embeddings.embed([CHUNK])[0],
            meta={"name": doc.name},
        )
    )
    tender = Tender(title="Salé : rénovation de l'éclairage public", organization="Commune de Salé")
    tender.analysis = TenderAnalysis(
        object="Rénovation de l'éclairage public", summary="Marché LED avec télégestion."
    )
    db.add(tender)
    db.flush()
    application = Application(tender_id=tender.id)
    application.documents.append(
        ApplicationDocument(
            document_type=template.document_type, title="Offre technique — Salé", template=template
        )
    )
    db.add(application)
    db.flush()
    return application.documents[0]


def _outputs(*contents: str) -> list[SectionOutput]:
    return [SectionOutput(content_md=c, used_sources=[], missing_info=[]) for c in contents]


def _service(db, fake_embeddings, responses) -> GenerationService:
    return GenerationService(db, FakeLLM(responses), KnowledgeBase(db, fake_embeddings))


def test_each_section_of_the_plan_is_written_in_order(db, fake_embeddings, document):
    service = _service(db, fake_embeddings, _outputs("## Contexte", "## Solution", "## Livrables"))

    service.generate_document(document)

    assert [s.key for s in document.sections] == ["contexte", "solution", "livrables"]
    assert [s.position for s in document.sections] == [0, 1, 2]
    assert [s.title for s in document.sections][1] == "Solution technique"
    assert all(s.status == SectionStatus.generated and s.generated_at for s in document.sections)
    assert document.status == AppDocStatus.draft and document.current_version == 1
    assert all(s.prompt_version == "v1" and s.model for s in document.sections)


def test_cited_extracts_become_sources_and_invented_ones_are_dropped(db, fake_embeddings, document):
    responses = [
        SectionOutput(content_md="Contexte", used_sources=[], missing_info=[]),
        SectionOutput(
            content_md="Nous avons déjà mené ce type de projet [S1].",
            used_sources=["S1", "S9"],
            missing_info=[],
        ),
        SectionOutput(content_md="Livrables", used_sources=[], missing_info=[]),
    ]
    _service(db, fake_embeddings, responses).generate_document(document)

    solution = next(s for s in document.sections if s.key == "solution")
    assert len(solution.sources) == 1  # « S9 » ne désigne aucun extrait : il ne devient pas une source
    source = solution.sources[0]
    assert source["kind"] == "chunk" and source["label"] == "Note-capacites.pdf p. 1"
    assert source["document_id"] and source["page"] == 1


def test_missing_information_is_kept_not_invented(db, fake_embeddings, document):
    responses = [
        SectionOutput(
            content_md="Le marché porte sur [À COMPLÉTER : nombre de points lumineux].",
            used_sources=[],
            missing_info=["nombre de points lumineux", "  "],
        ),
        *_outputs("Solution", "Livrables"),
    ]
    _service(db, fake_embeddings, responses).generate_document(document)

    contexte = next(s for s in document.sections if s.key == "contexte")
    assert contexte.missing_info == ["nombre de points lumineux"]  # les entrées vides sont écartées
    assert "[À COMPLÉTER" in contexte.content_md


def test_a_failed_section_does_not_lose_the_document(db, fake_embeddings, document):
    llm = FakeLLM([SectionOutput(content_md="Contexte", used_sources=[], missing_info=[])])  # une seule
    service = GenerationService(db, llm, KnowledgeBase(db, fake_embeddings))

    service.generate_document(document)

    sections = {s.key: s for s in document.sections}
    assert sections["contexte"].content_md == "Contexte"
    assert sections["solution"].content_md.startswith(FAILED_PREFIX)
    assert sections["livrables"].content_md.startswith(FAILED_PREFIX)
    assert sections["solution"].missing_info == ["Section à reprendre : Solution technique"]
    assert document.status == AppDocStatus.draft  # ce qui est écrit vaut d'être relu


def test_unverifiable_claims_are_reported_on_the_document(db, fake_embeddings, document):
    responses = _outputs(
        "La Commune de Salé souhaite rénover son éclairage public.",
        "Nos équipes certifiées ISO 27001 interviennent pour la Société Générale Marocaine.",
        "Livrables",
    )
    _service(db, fake_embeddings, responses).generate_document(document)

    assert len(document.warnings) == 2
    assert any("ISO 27001" in w for w in document.warnings)
    assert any("Société Générale Marocaine" in w for w in document.warnings)
    # l'organisme acheteur est cité sans être un client : ce n'est pas une invention
    assert not any("Commune de Salé" in w for w in document.warnings)
    assert all(
        w.startswith("Contexte et enjeux —") or w.startswith("Solution technique —")
        for w in document.warnings
    )


def test_generating_again_replaces_the_sections_and_bumps_the_version(db, fake_embeddings, document):
    _service(db, fake_embeddings, _outputs("A", "B", "C")).generate_document(document)
    _service(db, fake_embeddings, _outputs("A2", "B2", "C2")).generate_document(document)

    assert [s.content_md for s in document.sections] == ["A2", "B2", "C2"]
    assert document.current_version == 2
    assert (
        db.scalar(select(ApplicationSection).where(ApplicationSection.key == "contexte")).content_md == "A2"
    )


def test_regenerate_one_section_with_an_instruction(db, fake_embeddings, document):
    _service(db, fake_embeddings, _outputs("A", "B", "C")).generate_document(document)
    section = next(s for s in document.sections if s.key == "solution")

    llm = FakeLLM([SectionOutput(content_md="Version plus courte.", used_sources=[], missing_info=[])])
    GenerationService(db, llm, KnowledgeBase(db, fake_embeddings)).regenerate_section(
        section, "Raccourcir et enlever le jargon"
    )

    assert section.content_md == "Version plus courte."
    prompt = llm.calls[0]["user"]
    assert "Raccourcir et enlever le jargon" in prompt and "TEXTE ACTUEL" in prompt
    assert [s.content_md for s in document.sections] == ["A", "Version plus courte.", "C"]


def test_generation_is_audited(db, fake_embeddings, document):
    _service(db, fake_embeddings, _outputs("A", "B", "C")).generate_document(document)
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "application_document.generated"))
    assert audit is not None and audit.payload["sections"] == 3 and audit.payload["failed"] == 0
    assert audit.payload["version"] == 1


def test_a_document_without_a_template_is_a_programming_error(db, fake_embeddings, document):
    document.template = None
    db.flush()
    with pytest.raises(ValueError, match="sans modèle"):
        _service(db, fake_embeddings, []).generate_document(document)
