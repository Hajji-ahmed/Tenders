"""Moteur d'éligibilité par règles : un jugement par catégorie d'exigence contre le profil de
l'entreprise (certifications, technologies, compétences, experts, projets, documents utilisables),
réponses utilisateur prioritaires, résumé (ratio, obligatoires non satisfaites — RB-003), persistance
et relance du score ; job et endpoints."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.models import (
    AuditLog,
    CompanyDocument,
    Expert,
    JobStatus,
    Priority,
    RequirementCategory,
    RequirementStatus,
    Skill,
    Tender,
    TenderRequirement,
)
from app.models.document import DocumentCategory, DocumentStatus
from app.services.eligibility import EligibilityEngine, EligibilitySummary

S = RequirementStatus
C = RequirementCategory


@dataclass
class Answer:
    id: object
    text: str


def _req(category: C, description: str, *, mandatory: bool = True, code: str = "X-001") -> TenderRequirement:
    return TenderRequirement(
        code=code,
        category=category,
        description=description,
        is_mandatory=mandatory,
        priority=Priority.IMPORTANTE,
    )


@pytest.fixture
def enriched(db, company):
    """InnoSustain + un expert, une compétence et deux documents (un utilisable, un expiré)."""
    today = date.today()
    company.experts.append(Expert(full_name="Nadia F.", role="Chef de projet énergie", years_experience=8))
    company.skills.append(Skill(name="Audit énergétique"))
    db.add_all(
        [
            CompanyDocument(
                company_id=company.id,
                name="Attestation fiscale 2026",
                category=DocumentCategory.attestation,
                storage_key="k1",
                mime_type="application/pdf",
                size_bytes=1,
                sha256="a" * 64,
                expires_at=today + timedelta(days=200),
                tags=["fiscale"],
            ),
            CompanyDocument(
                company_id=company.id,
                name="Attestation CNSS",
                category=DocumentCategory.attestation,
                storage_key="k2",
                mime_type="application/pdf",
                size_bytes=1,
                sha256="b" * 64,
                status=DocumentStatus.expired,
                expires_at=today - timedelta(days=10),
                tags=[],
            ),
        ]
    )
    db.flush()
    return company


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(
        title="Éclairage public de Salé", sector="Énergie", extra={"technologies": ["Python", "Kafka"]}
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def rules(db, enriched, tender) -> EligibilityEngine:
    rules = EligibilityEngine(db, enriched)
    rules.tender = tender  # contexte des règles : secteur, technologies demandées par l'annonce
    return rules


def test_certification_valid_expired_or_missing(rules, tender):
    ok = rules.judge(_req(C.certification, "Certification ISO 14001 en cours de validité"), [])
    assert (
        ok.status == S.CONFORME
        and ok.evidence[0].kind == "certification"
        and "ISO 14001" in ok.evidence[0].label
    )
    expired = rules.judge(_req(C.certification, "Certification ISO 9001 exigée"), [])
    assert (
        expired.status == S.NON_CONFORME
        and "ISO 9001" in expired.justification
        and "expirée le" in expired.justification
    )
    missing = rules.judge(_req(C.certification, "Certification ISO 27001 exigée"), [])
    assert missing.status == S.INFO_MANQUANTE and missing.evidence == []


def test_technique_all_partial_or_undetectable(rules, tender):
    full = rules.judge(_req(C.technique, "Développement en Python avec base PostgreSQL"), [])
    assert full.status == S.CONFORME and {e.kind for e in full.evidence} == {"technology"}
    partial = rules.judge(_req(C.technique, "Maîtrise de Python et de Kafka"), [])
    assert partial.status == S.A_VERIFIER and "Kafka" in partial.justification
    skill = rules.judge(_req(C.technique, "Réalisation d'un audit énergétique préalable"), [])
    assert skill.status == S.CONFORME and skill.evidence[0].kind == "skill"
    none = rules.judge(_req(C.technique, "Programmation embarquée en Rust"), [])
    assert none.status == S.INFO_MANQUANTE


def test_experience_counts_projects_or_expert_years(rules, tender):
    # secteur Énergie : 1 projet (Audit énergétique)
    enough = rules.judge(_req(C.experience, "Au moins 1 référence similaire"), [])
    assert enough.status == S.CONFORME and enough.evidence[0].kind == "project"
    short = rules.judge(
        _req(C.experience, "Au moins deux références similaires (2 projets) de plus de 3 000 points"), []
    )
    assert short.status == S.NON_CONFORME and "1 projet" in short.justification and "2" in short.justification
    years = rules.judge(_req(C.experience, "5 ans d'expérience minimum dans le domaine"), [])
    assert (
        years.status == S.CONFORME and years.evidence[0].kind == "expert" and "8 ans" in years.justification
    )
    too_many = rules.judge(_req(C.experience, "15 années d'expérience"), [])
    assert too_many.status == S.NON_CONFORME
    vague = rules.judge(_req(C.experience, "Expérience significative dans des projets comparables"), [])
    assert vague.status == S.INFO_MANQUANTE


def test_team_role_matches_an_expert(rules, tender):
    found = rules.judge(_req(C.equipe, "Un chef de projet énergie dédié à la mission"), [])
    assert (
        found.status == S.CONFORME
        and found.evidence[0].kind == "expert"
        and "Nadia" in found.evidence[0].label
    )
    missing = rules.judge(_req(C.equipe, "Un ingénieur cybersécurité senior"), [])
    assert missing.status == S.INFO_MANQUANTE


def test_administrative_documents_usable_expired_or_missing(rules, tender):
    ok = rules.judge(_req(C.administrative, "Attestation fiscale de moins d'un an"), [])
    assert ok.status == S.CONFORME and ok.evidence[0].kind == "document" and "fiscale" in ok.evidence[0].label
    expired = rules.judge(_req(C.administrative, "Attestation CNSS en cours de validité"), [])
    assert expired.status == S.NON_CONFORME and "expiré" in expired.justification.lower()
    missing = rules.judge(_req(C.juridique, "Extrait du registre de commerce"), [])
    assert missing.status == S.INFO_MANQUANTE
    financial = rules.judge(_req(C.financiere, "Bilan des trois derniers exercices"), [])
    assert financial.status == S.INFO_MANQUANTE


def test_generic_words_do_not_match_documents(db, company, tender):
    """Constaté en réel : « attestation CNSS » et « visite obligatoire » étaient rapprochés d'une
    « Attestation fiscale » (mot « attestation », tag « obligatoire »)."""
    db.add(
        CompanyDocument(
            company_id=company.id,
            name="Attestation fiscale 2025",
            category=DocumentCategory.attestation,
            storage_key="k",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="c" * 64,
            tags=["obligatoire", "fiscale"],
        )
    )
    db.flush()
    rules = EligibilityEngine(db, company)
    rules.tender = tender
    assert rules.judge(_req(C.administrative, "Fournir une attestation CNSS"), []).status == S.INFO_MANQUANTE
    assert (
        rules.judge(_req(C.administrative, "Visite des lieux obligatoire le 15 octobre"), []).status
        == S.INFO_MANQUANTE
    )
    assert (
        rules.judge(_req(C.administrative, "Attestation fiscale de moins d'un an"), []).status == S.CONFORME
    )


def test_experience_numbers_are_read_without_accents(rules, tender):
    plain = rules.judge(
        _req(C.experience, "Justifier d'au moins deux references similaires de plus de 3 000 points"), []
    )
    assert plain.status == S.NON_CONFORME and "2 requis" in plain.justification


def test_methodology_and_other_need_a_human(rules, tender):
    assert rules.judge(_req(C.methodologie, "Note méthodologique détaillée"), []).status == S.A_VERIFIER
    assert rules.judge(_req(C.autre, "Validité des offres de 90 jours"), []).status == S.A_VERIFIER


def test_user_answer_takes_precedence(rules, tender):
    req = _req(C.equipe, "Deux experts cybersécurité certifiés")
    yes = rules.judge(req, [Answer(uuid4(), "Oui, 2 experts disponibles")])
    assert yes.status == S.CONFORME and yes.evidence[0].kind == "answer"
    no = rules.judge(req, [Answer(uuid4(), "Non, pas de profil de ce type")])
    assert no.status == S.NON_CONFORME
    unsure = rules.judge(req, [Answer(uuid4(), "À confirmer avec le partenaire")])
    assert unsure.status == S.A_VERIFIER
    latest = rules.judge(req, [Answer(uuid4(), "Non"), Answer(uuid4(), "Finalement oui")])
    assert latest.status == S.CONFORME  # la dernière réponse compte


def test_evaluate_persists_summary_flags_mandatory_unmet_and_refreshes_score(
    db, enriched, tender, monkeypatch
):
    tender.requirements.extend(
        [
            _req(C.certification, "Certification ISO 14001", code="CERT-001"),
            _req(C.certification, "Certification ISO 27001", code="CERT-002"),  # obligatoire, manquante
            _req(
                C.administrative, "Attestation CNSS", code="ADM-001", mandatory=False
            ),  # non conforme, facultative
            _req(C.methodologie, "Note méthodologique", code="METH-001"),
            _req(C.technique, "Python", code="TECH-001"),
        ]
    )
    manual = tender.requirements[3]
    manual.status, manual.justification, manual.manual_status = S.CONFORME, "Validé en réunion", True
    db.flush()
    flagged: list[tuple[str, str]] = []
    engine = EligibilityEngine(
        db, enriched, llm=FakeLLM(), on_mandatory_unmet=lambda t, r: flagged.append((t.title, r.code))
    )

    summary = engine.evaluate(tender)

    assert isinstance(summary, EligibilitySummary) and summary.total == 5
    assert summary.by_status == {"CONFORME": 3, "A_VERIFIER": 0, "NON_CONFORME": 1, "INFO_MANQUANTE": 1}
    assert summary.mandatory_unmet == ["CERT-002"] and summary.ratio == 0.6
    by_code = {r.code: r for r in tender.requirements}
    assert (
        by_code["CERT-001"].status == S.CONFORME
        and by_code["CERT-001"].evidence[0]["kind"] == "certification"
    )
    assert (
        by_code["METH-001"].status == S.CONFORME and by_code["METH-001"].justification == "Validé en réunion"
    )  # manuel conservé
    assert by_code["ADM-001"].status == S.NON_CONFORME
    assert tender.extra["eligibility"]["ratio"] == 0.6 and tender.extra["eligibility"]["mandatory_unmet"] == [
        "CERT-002"
    ]
    assert flagged == [("Éclairage public de Salé", "CERT-002")]
    assert tender.score is not None
    eligibility = next(s for s in tender.score.breakdown if s["key"] == "eligibility")
    assert eligibility["score"] == 60.0  # le score repart avec le ratio d'éligibilité
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.eligibility_evaluated"))
    assert audit is not None and audit.payload["mandatory_unmet"] == ["CERT-002"]


def test_evaluate_without_requirements_is_fully_eligible(db, enriched, tender):
    summary = EligibilityEngine(db, enriched, llm=FakeLLM()).evaluate(tender)
    assert summary.total == 0 and summary.ratio == 1.0 and summary.mandatory_unmet == []


def test_eligibility_job_and_endpoints(auth_client, db, run_jobs_inline, enriched, tender, fake_llm):
    tender.requirements.append(_req(C.certification, "Certification ISO 14001", code="CERT-001"))
    db.flush()
    assert auth_client.get(f"/api/v1/tenders/{tender.id}/eligibility").status_code == 404

    r = auth_client.post(f"/api/v1/tenders/{tender.id}/eligibility")
    assert r.status_code == 202, r.text
    assert r.json()["type"] == "evaluate_eligibility"
    job = auth_client.get(f"/api/v1/jobs/{r.json()['id']}").json()
    assert job["status"] == JobStatus.done and job["result"]["ratio"] == 1.0

    body = auth_client.get(f"/api/v1/tenders/{tender.id}/eligibility").json()
    assert body["total"] == 1 and body["by_status"]["CONFORME"] == 1 and body["ratio"] == 1.0
    assert body["mandatory_unmet"] == [] and body["evaluated_at"]
