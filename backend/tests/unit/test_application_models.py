"""Modèles du dossier de candidature (Task 9.1) : un dossier par appel d'offres, ses documents et
leurs sections ; suppression en cascade et clés de section uniques par document."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    AppDocStatus,
    Application,
    ApplicationDocument,
    ApplicationSection,
    ApplicationStatus,
    DocumentType,
    SectionSource,
    SectionStatus,
    Template,
    Tender,
)


@pytest.fixture
def template(db) -> Template:
    return _template(db)


def _template(db, **over) -> Template:
    t = Template(
        name=over.pop("name", "Lettre de candidature"),
        document_type=over.pop("document_type", DocumentType.lettre_candidature),
        description="Lettre adressée à l'organisme",
        sections=[
            {
                "key": "objet",
                "title": "Objet et référence",
                "instructions": "Rappeler l'objet du marché et sa référence.",
                "max_words": 120,
                "requires": [SectionSource.tender_analysis],
            },
            {
                "key": "adequation",
                "title": "Synthèse de l'adéquation",
                "instructions": "Montrer en quoi l'entreprise répond aux exigences.",
                "max_words": 250,
                "requires": [SectionSource.company_facts, SectionSource.requirements],
            },
        ],
        is_default=True,
        **over,
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="Éclairage public de Salé")
    db.add(t)
    db.flush()
    return t


def _application(db, tender, template) -> Application:
    app = Application(tender_id=tender.id)
    doc = ApplicationDocument(
        document_type=template.document_type, title="Lettre de candidature", template=template
    )
    doc.sections.append(
        ApplicationSection(key="objet", title="Objet et référence", position=0, content_md="# Objet")
    )
    app.documents.append(doc)
    db.add(app)
    db.flush()
    return app


def test_template_holds_its_section_plan(db, template):
    stored = db.get(Template, template.id)
    assert stored.language == "fr" and stored.version == 1 and stored.is_default is True
    assert [s["key"] for s in stored.sections] == ["objet", "adequation"]
    assert stored.sections[1]["requires"] == ["company_facts", "requirements"]
    assert stored.repeat_for is None


def test_repeatable_template_names_what_it_repeats_over(db):
    cv = _template(db, name="CV", document_type=DocumentType.cv, repeat_for="experts")
    assert db.get(Template, cv.id).repeat_for == "experts"


def test_application_defaults_and_relations(db, tender, template):
    app = _application(db, tender, template)

    assert app.status == ApplicationStatus.draft and app.submitted_at is None
    assert tender.application is app
    doc = app.documents[0]
    assert doc.status == AppDocStatus.pending and doc.current_version == 0 and doc.warnings == []
    assert doc.template is template and doc.document_type == DocumentType.lettre_candidature
    section = doc.sections[0]
    assert section.status == SectionStatus.generated and section.sources == []
    assert section.missing_info == [] and section.generated_at is not None


def test_application_unique_per_tender(db, tender, template):
    _application(db, tender, template)
    db.add(Application(tender_id=tender.id))
    with pytest.raises(IntegrityError):
        db.flush()


def test_section_key_is_unique_within_a_document(db, tender, template):
    app = _application(db, tender, template)
    app.documents[0].sections.append(ApplicationSection(key="objet", title="Doublon", position=1))
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_a_tender_removes_its_application_documents_and_sections(db, tender, template):
    _application(db, tender, template)
    db.delete(tender)
    db.flush()

    assert db.scalar(select(func.count(Application.id))) == 0
    assert db.scalar(select(func.count(ApplicationDocument.id))) == 0
    assert db.scalar(select(func.count(ApplicationSection.id))) == 0
    assert db.scalar(select(func.count(Template.id))) == 1  # le modèle, lui, reste


def test_deleting_a_template_keeps_the_documents_it_shaped(db, tender, template):
    app = _application(db, tender, template)
    db.delete(template)
    db.flush()
    db.refresh(app.documents[0])

    assert app.documents[0].template_id is None  # un document déjà rédigé survit à son modèle
    assert app.documents[0].document_type == DocumentType.lettre_candidature
