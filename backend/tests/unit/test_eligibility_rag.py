"""Éligibilité étayée par la base documentaire (Task 8.4) : ce que les règles n'ont pu trancher est
repris par le modèle, qui ne lit QUE des extraits de documents utilisables et doit citer ses sources.
Garde-fou : pas de CONFORME sans preuve citée et existante — sinon le statut est rétrogradé."""

from datetime import date, timedelta

import pytest

from app.ai.llm import FakeLLM
from app.ai.outputs import EligibilityJudgement
from app.models import (
    DocumentChunk,
    Priority,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderRequirement,
)
from app.models.document import CompanyDocument, DocumentCategory, DocumentStatus
from app.services.eligibility import EligibilityEngine
from app.services.knowledge import KnowledgeBase

S = RequirementStatus
C = RequirementCategory

ISO_TEXT = "Certificat ISO 27001 délivré à InnoSustain le 12/01/2025, valable jusqu'au 31 décembre 2027."
CAPACITY_TEXT = "InnoSustain a réalisé la télégestion de 4 200 points lumineux pour la ville de Fès."


def _req(category: C, description: str, *, code="X-001", status=S.INFO_MANQUANTE) -> TenderRequirement:
    return TenderRequirement(
        code=code,
        category=category,
        description=description,
        is_mandatory=True,
        priority=Priority.CRITIQUE,
        status=status,
    )


def _doc(db, company, name, category, text, embeddings, **over) -> CompanyDocument:
    doc = CompanyDocument(
        company_id=company.id,
        name=name,
        category=category,
        storage_key=f"company/{name}",
        mime_type="application/pdf",
        size_bytes=1,
        sha256=f"{abs(hash(name)):064d}"[:64],
        **over,
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
            content=text,
            embedding=embeddings.embed([text])[0],
            meta={"category": str(category), "name": name, "expires_at": None, "version": 1},
        )
    )
    db.flush()
    return doc


@pytest.fixture
def base(db, company, fake_embeddings):
    """Un certificat indexé (utilisable) et une note de capacités indexée mais archivée."""
    iso = _doc(
        db,
        company,
        "ISO-27001.pdf",
        DocumentCategory.certification,
        ISO_TEXT,
        fake_embeddings,
        expires_at=date.today() + timedelta(days=400),
    )
    archived = _doc(
        db,
        company,
        "Note-capacites.pdf",
        DocumentCategory.presentation,
        CAPACITY_TEXT,
        fake_embeddings,
        status=DocumentStatus.archived,
    )
    tender = Tender(title="Éclairage public de Salé", sector="Énergie")
    db.add(tender)
    db.flush()
    return {"iso": iso, "archived": archived, "tender": tender, "kb": KnowledgeBase(db, fake_embeddings)}


def _engine(db, company, base, llm) -> EligibilityEngine:
    engine = EligibilityEngine(db, company, llm=llm, kb=base["kb"])
    engine.tender = base["tender"]
    return engine


def _judge_calls(llm: FakeLLM) -> list[dict]:
    """Seulement les appels de jugement : `evaluate` relance aussi le score, qui interroge le modèle."""
    return [c for c in llm.calls if c["output"] is EligibilityJudgement]


def test_a_cited_document_makes_the_requirement_compliant(db, company, base):
    """Les règles ne voient pas la certification (pas de ligne au profil) ; le document, si."""
    llm = FakeLLM(
        [
            EligibilityJudgement(
                status=S.CONFORME,
                justification="Le certificat ISO 27001 est valable jusqu'au 31/12/2027.",
                evidence_refs=["S1"],
            )
        ]
    )
    req = _req(C.certification, ISO_TEXT)
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.CONFORME and "31/12/2027" in (req.justification or "")
    evidence = req.evidence[0]
    assert evidence["kind"] == "chunk" and evidence["label"] == "ISO-27001.pdf p. 1"
    assert evidence["id"]  # identifiant du morceau : la preuve est retrouvable
    # la pièce d'où vient l'extrait, pour l'ouvrir à la bonne page depuis la fiche (8.5)
    assert evidence["document_id"] == str(base["iso"].id) and evidence["page"] == 1
    prompt = _judge_calls(llm)[0]["user"]
    assert "[S1] (ISO-27001.pdf p. 1)" in prompt and ISO_TEXT[:40] in prompt


def test_compliant_without_a_citation_is_downgraded(db, company, base):
    """Garde-fou RB-005 : une conformité affirmée sans preuve citée n'est pas une conformité."""
    llm = FakeLLM(
        [
            EligibilityJudgement(
                status=S.CONFORME, justification="L'entreprise est certifiée.", evidence_refs=[]
            )
        ]
    )
    req = _req(C.certification, ISO_TEXT)
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.A_VERIFIER and "preuve non fournie" in (req.justification or "").lower()
    assert req.evidence == []


def test_a_citation_pointing_nowhere_is_refused_too(db, company, base):
    llm = FakeLLM(
        [EligibilityJudgement(status=S.CONFORME, justification="Voir le dossier.", evidence_refs=["S7"])]
    )
    req = _req(C.certification, ISO_TEXT)
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.A_VERIFIER and "preuve non fournie" in (req.justification or "").lower()


def test_the_model_may_also_conclude_that_nothing_matches(db, company, base):
    llm = FakeLLM(
        [
            EligibilityJudgement(
                status=S.INFO_MANQUANTE,
                justification="Aucun extrait ne parle d'assurance décennale.",
                evidence_refs=[],
            )
        ]
    )
    req = _req(C.juridique, "Attestation d'assurance décennale")
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.INFO_MANQUANTE and "décennale" in (req.justification or "")


def test_non_compliance_without_a_citation_becomes_a_missing_information(db, company, base):
    """L'absence de preuve n'est pas la preuve d'une absence : constaté en réel, le modèle déclarait
    « non conforme » faute d'extrait sur un acte d'engagement — c'est une information à demander."""
    llm = FakeLLM(
        [
            EligibilityJudgement(
                status=S.NON_CONFORME,
                justification="Aucun extrait ne contient un acte d'engagement.",
                evidence_refs=[],
            )
        ]
    )
    req = _req(C.financiere, "Fournir un acte d'engagement et un bordereau des prix")
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.INFO_MANQUANTE and req.evidence == []


def test_nothing_found_means_nothing_cited(db, company, base):
    """Le modèle cite parfois des extraits qu'il vient d'écarter : une information manquante ne
    s'accompagne d'aucune preuve, sinon la colonne « preuves » affiche des documents hors sujet."""
    llm = FakeLLM(
        [
            EligibilityJudgement(
                status=S.INFO_MANQUANTE,
                justification="Aucun extrait ne mentionne une assurance décennale.",
                evidence_refs=["S1"],
            )
        ]
    )
    req = _req(C.juridique, "Attestation d'assurance décennale")
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.INFO_MANQUANTE and req.evidence == []


def test_unusable_documents_never_reach_the_model(db, company, base):
    """RB-007 : la note de capacités est archivée — son contenu ne doit pas servir de preuve."""
    llm = FakeLLM(
        [
            EligibilityJudgement(
                status=S.INFO_MANQUANTE, justification="Rien dans les documents.", evidence_refs=[]
            )
        ]
    )
    req = _req(C.experience, CAPACITY_TEXT)
    base["tender"].requirements.append(req)
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert "Note-capacites.pdf" not in _judge_calls(llm)[0]["user"]
    assert req.status == S.INFO_MANQUANTE


def test_rules_that_concluded_are_left_alone(db, company, base):
    """Le modèle n'est appelé que pour ce que les règles n'ont pas tranché : ni CONFORME, ni
    NON_CONFORME, ni statut manuel, ni jugement fondé sur une réponse de l'utilisateur."""
    llm = FakeLLM([])  # aucun appel scripté : un appel ferait échouer le test
    conforme = _req(C.certification, "Certification ISO 14001", code="CERT-001", status=S.CONFORME)
    manual = _req(C.autre, "Validité des offres", code="AUT-001", status=S.A_VERIFIER)
    manual.manual_status = True
    base["tender"].requirements.extend([conforme, manual])
    db.flush()

    _engine(db, company, base, llm).evaluate(base["tender"])

    assert _judge_calls(llm) == []
    assert conforme.status == S.CONFORME and manual.status == S.A_VERIFIER


def test_a_model_failure_leaves_the_rule_verdict_in_place(db, company, base):
    llm = FakeLLM([])  # plus aucune réponse : le fournisseur lève
    req = _req(C.juridique, "Extrait du registre de commerce")
    base["tender"].requirements.append(req)
    db.flush()

    summary = _engine(db, company, base, llm).evaluate(base["tender"])

    assert req.status == S.INFO_MANQUANTE and summary.total == 1
    assert "base documentaire" in (req.justification or "")  # la justification des règles est conservée


def test_without_a_knowledge_base_the_engine_stays_rule_only(db, company, base):
    """Phase 7 inchangée : sans `kb`, aucun appel au modèle pour juger une exigence."""
    llm = FakeLLM([])
    req = _req(C.juridique, "Extrait du registre de commerce")
    base["tender"].requirements.append(req)
    db.flush()

    engine = EligibilityEngine(db, company, llm=llm)
    engine.tender = base["tender"]
    engine.evaluate(base["tender"])

    assert _judge_calls(llm) == [] and req.status == S.INFO_MANQUANTE
