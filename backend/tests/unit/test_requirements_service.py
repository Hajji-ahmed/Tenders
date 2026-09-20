"""Extraction structurée des exigences : un appel par pièce, fusion et déduplication, codes
séquentiels par catégorie (TECH-001, ADM-001…), source résolue, ré-extraction qui conserve les
statuts saisis à la main et supprime les exigences disparues."""

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.ai.outputs import RequirementOutput, RequirementsOutput
from app.models import (
    AuditLog,
    DownloadStatus,
    ExtractionStatus,
    Priority,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderDocument,
    TenderRequirement,
)
from app.services.requirements import RequirementsService, next_code

PDF = "application/pdf"


def _doc(name: str, pages: list[str]) -> TenderDocument:
    return TenderDocument(
        name=name,
        mime_type=PDF,
        download_status=DownloadStatus.done,
        extraction_status=ExtractionStatus.done,
        extracted_text="\f".join(pages),
        page_count=len(pages),
    )


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="Rénovation de l'éclairage public de Salé")
    t.documents.append(_doc("RC.pdf", ["Article 4 : conditions.", "Article 5 : pièces."]))
    t.documents.append(_doc("CCTP.pdf", ["Luminaires LED IP66, garantie 5 ans."]))
    t.documents.append(TenderDocument(name="scan.pdf", extraction_status=ExtractionStatus.failed))
    db.add(t)
    db.flush()
    return t


def _req(category: RequirementCategory, description: str, **over) -> RequirementOutput:
    base = dict(
        category=category,
        description=description,
        is_mandatory=True,
        evidence_required=None,
        priority=Priority.IMPORTANTE,
        source_document=None,
        source_page=1,
        source_excerpt=None,
    )
    base.update(over)
    return RequirementOutput(**base)


def _llm_by_document(**per_doc: RequirementsOutput) -> FakeLLM:
    """Réponse choisie d'après le nom de pièce cité dans le prompt."""

    def respond(user: str, output):
        for name, response in per_doc.items():
            if f"PIÈCE : {name}" in user:
                return response
        return RequirementsOutput(requirements=[])

    return FakeLLM(respond)


def test_extract_merges_near_duplicates_and_assigns_sequential_codes(db, tender):
    llm = _llm_by_document(
        **{
            "RC.pdf": RequirementsOutput(
                requirements=[
                    _req(
                        RequirementCategory.technique,
                        "Fournir des luminaires LED IP66 garantis 5 ans",
                        source_page=2,
                        source_excerpt="luminaires LED IP66",
                    ),
                    _req(
                        RequirementCategory.administrative,
                        "Attestation fiscale de moins d'un an",
                        priority=Priority.CRITIQUE,
                        evidence_required="Attestation fiscale",
                    ),
                    _req(
                        RequirementCategory.experience,
                        "Deux références similaires de plus de 3 000 points lumineux",
                        is_mandatory=False,
                        priority=Priority.FACULTATIVE,
                    ),
                ]
            ),
            "CCTP.pdf": RequirementsOutput(
                requirements=[
                    _req(
                        RequirementCategory.technique,
                        "Luminaires LED IP66 garantis 5 ans à fournir",
                        source_page=1,
                    ),  # doublon de RC (mots réordonnés)
                    _req(
                        RequirementCategory.technique,
                        "Système de télégestion compatible DALI",
                        source_document="CCTP.pdf",
                        source_page=1,
                    ),
                ]
            ),
        }
    )

    reqs = RequirementsService(db, llm).extract(tender)

    assert [(r.code, r.description[:20]) for r in reqs] == [
        ("TECH-001", "Fournir des luminair"),
        ("ADM-001", "Attestation fiscale "),
        ("EXP-001", "Deux références simi"),
        ("TECH-002", "Système de télégesti"),
    ]
    assert all(r.status == RequirementStatus.A_VERIFIER and r.manual_status is False for r in reqs)
    by_code = {r.code: r for r in reqs}
    rc = next(d for d in tender.documents if d.name == "RC.pdf")
    cctp = next(d for d in tender.documents if d.name == "CCTP.pdf")
    assert by_code["TECH-001"].source_document_id == rc.id and by_code["TECH-001"].source_page == 2
    assert by_code["TECH-001"].source_excerpt == "luminaires LED IP66"
    assert by_code["TECH-002"].source_document_id == cctp.id
    assert (
        by_code["ADM-001"].priority == Priority.CRITIQUE
        and by_code["ADM-001"].evidence_required == "Attestation fiscale"
    )
    assert by_code["EXP-001"].is_mandatory is False
    # deux appels : un par pièce lisible, le scan est ignoré
    assert [c["output"].__name__ for c in llm.calls] == ["RequirementsOutput", "RequirementsOutput"]
    assert "=== RC.pdf — page 2 ===" in llm.calls[0]["user"] and "PIÈCE : CCTP.pdf" in llm.calls[1]["user"]
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.requirements_extracted"))
    assert audit is not None and audit.payload == {
        "extracted": 5,
        "kept": 4,
        "created": 4,
        "updated": 0,
        "deleted": 0,
    }


def test_reextraction_keeps_manual_status_and_ids_and_drops_vanished_requirements(db, tender):
    first = _llm_by_document(
        **{
            "RC.pdf": RequirementsOutput(
                requirements=[
                    _req(RequirementCategory.technique, "Fournir des luminaires LED IP66"),
                    _req(RequirementCategory.administrative, "Attestation fiscale de moins d'un an"),
                ]
            )
        }
    )
    service = RequirementsService(db, first)
    reqs = service.extract(tender)
    tech, adm = reqs
    tech.status, tech.justification, tech.manual_status = (
        RequirementStatus.CONFORME,
        "Gamme LED IP66 au catalogue",
        True,
    )
    adm.status = RequirementStatus.NON_CONFORME  # posé par le moteur, pas à la main
    db.flush()

    second = _llm_by_document(
        **{
            "RC.pdf": RequirementsOutput(
                requirements=[
                    _req(
                        RequirementCategory.technique, "Fournir des luminaires LED IP66 ", source_page=2
                    ),  # ≈ identique
                    _req(RequirementCategory.technique, "Garantie constructeur de 5 ans"),  # nouvelle
                ]
            )
        }
    )
    again = RequirementsService(db, second).extract(tender)

    assert [r.code for r in again] == ["TECH-001", "TECH-002"]
    kept = again[0]
    assert kept.id == tech.id and kept.status == RequirementStatus.CONFORME
    assert kept.justification == "Gamme LED IP66 au catalogue" and kept.source_page == 2
    assert db.get(TenderRequirement, adm.id) is None  # disparue : supprimée (statut moteur non conservé)
    assert (
        db.scalar(select(TenderRequirement).where(TenderRequirement.code == "TECH-002")).status
        == RequirementStatus.A_VERIFIER
    )


def test_matched_requirement_without_manual_status_is_reset(db, tender):
    llm = _llm_by_document(
        **{
            "RC.pdf": RequirementsOutput(
                requirements=[_req(RequirementCategory.juridique, "Ne pas être en redressement judiciaire")]
            )
        }
    )
    (req,) = RequirementsService(db, llm).extract(tender)
    req.status, req.justification = RequirementStatus.NON_CONFORME, "posé par le moteur"
    db.flush()
    (again,) = RequirementsService(db, llm).extract(tender)
    assert again.id == req.id and again.code == "JUR-001"
    assert again.status == RequirementStatus.A_VERIFIER and again.justification is None


def test_extract_without_readable_document_gives_nothing_and_a_failing_document_is_skipped(db):
    t = Tender(title="Sans pièces")
    db.add(t)
    db.flush()
    assert RequirementsService(db, FakeLLM()).extract(t) == []

    t.documents.append(_doc("RC.pdf", ["texte"]))
    t.documents.append(_doc("CCTP.pdf", ["texte"]))
    db.flush()

    def respond(user: str, output):
        if "PIÈCE : RC.pdf" in user:
            raise RuntimeError("quota dépassé")
        return RequirementsOutput(
            requirements=[_req(RequirementCategory.equipe, "Un chef de projet certifié PMP")]
        )

    reqs = RequirementsService(db, FakeLLM(respond)).extract(t)
    assert [r.code for r in reqs] == ["EQU-001"]  # RC en échec, CCTP exploité


def test_next_code_continues_per_prefix():
    assert next_code("TECH", []) == "TECH-001"
    assert next_code("TECH", ["TECH-001", "ADM-004", "TECH-007"]) == "TECH-008"
    assert next_code("ADM", ["TECH-001", "ADM-004"]) == "ADM-005"
