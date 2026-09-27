"""Modèles de documents par défaut (Task 9.2) : les dix documents de la candidature, leur plan de
sections et ce que chaque section a le droit de lire. Le semis est rejouable sans rien écraser."""

from sqlalchemy import func, select

from app.models import DocumentType, SectionSource, Template
from app.services.templates import DEFAULT_TEMPLATES, section_keys, seed_templates

SOURCES = {s.value for s in SectionSource}


def test_ten_default_templates_one_per_document_type():
    assert len(DEFAULT_TEMPLATES) == len(DocumentType)
    assert {t["document_type"] for t in DEFAULT_TEMPLATES} == set(DocumentType)


def test_every_section_is_usable_by_the_generator():
    for template in DEFAULT_TEMPLATES:
        keys = section_keys(template["sections"])
        assert keys and len(keys) == len(set(keys)), template["name"]
        for section in template["sections"]:
            assert section["title"] and section["instructions"].strip()
            assert 60 <= section["max_words"] <= 800, (template["name"], section["key"])
            assert section["requires"], (template["name"], section["key"])  # rien ne s'écrit sans source
            assert set(section["requires"]) <= SOURCES, section["requires"]


def test_repeatable_templates_are_the_ones_that_speak_of_a_person_or_a_project():
    repeated = {t["document_type"]: t.get("repeat_for") for t in DEFAULT_TEMPLATES if t.get("repeat_for")}
    assert repeated == {DocumentType.cv: "experts", DocumentType.references: "projects"}


def test_the_declaration_never_invents_missing_data():
    declaration = next(t for t in DEFAULT_TEMPLATES if t["document_type"] == DocumentType.declaration)
    instructions = " ".join(s["instructions"] for s in declaration["sections"])
    assert "[À COMPLÉTER]" in instructions


def test_seed_creates_the_templates_and_is_idempotent(db):
    created = seed_templates(db)
    again = seed_templates(db)

    assert len(created) == len(DEFAULT_TEMPLATES) and again == []
    assert db.scalar(select(func.count(Template.id))) == len(DEFAULT_TEMPLATES)
    letter = db.scalar(select(Template).where(Template.document_type == DocumentType.lettre_candidature))
    assert letter.is_default is True and letter.language == "fr" and letter.version == 1
    spec = next(t for t in DEFAULT_TEMPLATES if t["document_type"] == DocumentType.lettre_candidature)
    assert [s["key"] for s in letter.sections] == section_keys(spec["sections"])


def test_seed_leaves_a_customised_template_alone(db):
    seed_templates(db)
    letter = db.scalar(select(Template).where(Template.document_type == DocumentType.lettre_candidature))
    letter.sections = [
        {"key": "objet", "title": "Objet", "instructions": "Le mien.", "max_words": 100, "requires": ["kb"]}
    ]
    letter.version = 2
    db.flush()

    assert seed_templates(db) == []
    db.refresh(letter)
    assert letter.version == 2 and [s["key"] for s in letter.sections] == ["objet"]
