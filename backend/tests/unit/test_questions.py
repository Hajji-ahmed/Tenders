"""Questions ciblées (FR-014 / FR-015) : une question par exigence INFO_MANQUANTE ou A_VERIFIER sans
question en cours, formulée par le modèle à partir de l'exigence et de ce que l'entreprise possède
déjà (priorité forcée CRITIQUE si obligatoire) ; répondre ré-évalue l'exigence liée et rafraîchit le
résumé d'éligibilité et le score ; ignorer ferme la question ; job `generate_questions`."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.ai.outputs import QuestionOutput
from app.models import (
    AuditLog,
    CompanyDocument,
    JobStatus,
    Priority,
    Question,
    QuestionStatus,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderRequirement,
)
from app.models.document import DocumentCategory
from app.services.eligibility import EligibilityEngine
from app.services.jobs import JobService
from app.services.questions import QuestionService

S = RequirementStatus
C = RequirementCategory


def _scripted() -> FakeLLM:
    """Le modèle formule une question qui cite le code de l'exigence lu dans le prompt."""

    def reply(user: str, output):
        code = next(line.split(" ", 1)[1] for line in user.splitlines() if line.startswith("CODE "))
        return QuestionOutput(text=f"Question précise sur {code} ?", priority=Priority.IMPORTANTE)

    return FakeLLM(reply)


@pytest.fixture
def tender(db, company) -> Tender:
    """Trois exigences : conforme, obligatoire sans information, facultative à vérifier."""
    db.add(
        CompanyDocument(
            company_id=company.id,
            name="Attestation fiscale 2026",
            category=DocumentCategory.attestation,
            storage_key="k1",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="a" * 64,
            expires_at=date.today() + timedelta(days=200),
            tags=["fiscale"],
        )
    )
    t = Tender(title="Éclairage public de Salé", sector="Énergie")
    t.requirements.extend(
        [
            TenderRequirement(
                code="CERT-001",
                category=C.certification,
                description="Certification ISO 14001",
                is_mandatory=True,
                priority=Priority.CRITIQUE,
                status=S.CONFORME,
            ),
            TenderRequirement(
                code="ADM-001",
                category=C.administrative,
                description="Attestation CNSS de moins de trois mois",
                is_mandatory=True,
                evidence_required="Attestation CNSS",
                priority=Priority.IMPORTANTE,
                status=S.INFO_MANQUANTE,
                justification="Aucun document correspondant dans la base documentaire",
            ),
            TenderRequirement(
                code="EXP-001",
                category=C.experience,
                description="Deux références similaires de plus de 3 000 points lumineux",
                is_mandatory=False,
                priority=Priority.FACULTATIVE,
                status=S.A_VERIFIER,
                justification="2 requis dans le secteur Énergie ; 1 projet au profil",
            ),
        ]
    )
    db.add(t)
    db.flush()
    return t


def _question(tender: Tender, code: str) -> Question:
    return next(q for q in tender.questions if q.requirement.code == code)


def test_generate_asks_one_question_per_open_requirement_and_does_not_duplicate(db, company, tender):
    llm = _scripted()

    questions = QuestionService(db, llm).generate(tender)

    assert [q.requirement.code for q in questions] == ["ADM-001", "EXP-001"]
    assert questions[0].priority == Priority.CRITIQUE  # obligatoire ⇒ forcée, quoi qu'en dise le modèle
    assert questions[1].priority == Priority.IMPORTANTE  # celle du modèle
    assert questions[0].text == "Question précise sur ADM-001 ?"
    assert all(q.status == QuestionStatus.open and q.tender_id == tender.id for q in questions)
    # le prompt porte l'exigence et ce que l'entreprise possède déjà dans la catégorie
    user = llm.calls[0]["user"]
    assert "Attestation CNSS de moins de trois mois" in user and "Attestation fiscale 2026" in user
    assert "Aucun document correspondant" in user  # le verdict des règles, pour formuler la question
    assert "Énergie" in llm.calls[1]["user"]  # exigence d'expérience : projets et secteur du profil

    assert QuestionService(db, llm).generate(tender) == []  # regénérer ne duplique pas
    assert len(tender.questions) == 2 and len(llm.calls) == 2
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "tender.questions_generated")).all()
    assert [a.payload["created"] for a in audit] == [2, 0]


def test_generate_falls_back_to_a_template_question_when_the_model_fails(db, company, tender):
    questions = QuestionService(db, FakeLLM()).generate(tender)  # aucune réponse scriptée ⇒ erreur

    assert len(questions) == 2
    text = questions[0].text
    assert "Attestation CNSS de moins de trois mois" in text and "Attestation CNSS" in text
    assert text.endswith("?") and questions[0].priority == Priority.CRITIQUE
    assert questions[1].priority == Priority.FACULTATIVE  # sans modèle : la priorité de l'exigence


def test_answer_rejudges_the_requirement_and_refreshes_summary_and_score(db, company, tender, user):
    service = QuestionService(db, _scripted())
    service.generate(tender)
    question = _question(tender, "ADM-001")
    req = question.requirement

    answer = service.answer(question, "Oui, attestation CNSS du 3 septembre 2026", user_id=user.id)

    assert question.status == QuestionStatus.answered and question.answer is answer
    assert answer.answer.startswith("Oui") and answer.answered_at is not None and answer.text == answer.answer
    assert req.status == S.CONFORME and req.evidence[0]["kind"] == "answer"
    assert req.justification is not None and "attestation CNSS du 3 septembre" in req.justification
    summary = tender.extra["eligibility"]
    assert summary["by_status"]["CONFORME"] == 2 and summary["mandatory_unmet"] == []
    assert tender.score is not None  # le score repart avec le nouveau ratio
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "question.answered"))
    assert audit is not None and audit.user_id == user.id and audit.payload["code"] == "ADM-001"

    # répondre à nouveau remplace la réponse (une seule par question) et re-juge
    service.answer(question, "Non, finalement l'attestation est expirée", user_id=user.id)
    assert question.answer.answer.startswith("Non") and req.status == S.NON_CONFORME
    assert len(tender.questions) == 2 and tender.extra["eligibility"]["mandatory_unmet"] == ["ADM-001"]
    assert (
        service.generate(tender) == []
    )  # non conforme par la réponse de l'utilisateur : on ne redemande pas


def test_generate_asks_about_rule_based_non_conformities_but_not_manual_ones(db, company, tender):
    """Une non-conformité constatée par les règles peut tenir à un profil incomplet (expert non saisi,
    attestation non déposée) : on demande. Un statut posé à la main est une décision : on se tait."""
    by_code = {r.code: r for r in tender.requirements}
    by_code["EXP-001"].status = S.NON_CONFORME
    by_code["EXP-001"].justification = "2 requis dans le secteur Énergie ; 1 projet au profil"
    by_code["ADM-001"].manual_status = True
    db.flush()

    questions = QuestionService(db, _scripted()).generate(tender)

    assert [q.requirement.code for q in questions] == ["EXP-001"]


def test_answers_feed_the_full_evaluation(db, company, tender, user):
    service = QuestionService(db, _scripted())
    service.generate(tender)
    service.answer(_question(tender, "ADM-001"), "Oui", user_id=user.id)

    by_requirement = QuestionService.answers_by_requirement(tender)
    assert [a.text for a in by_requirement[_question(tender, "ADM-001").requirement_id]] == ["Oui"]
    EligibilityEngine(db, company, llm=FakeLLM()).evaluate(tender, by_requirement)
    req = _question(tender, "ADM-001").requirement
    assert req.status == S.CONFORME  # la réponse prime sur la règle (aucun document CNSS au profil)


def test_skip_closes_the_question_and_leaves_the_requirement(db, company, tender):
    service = QuestionService(db, _scripted())
    service.generate(tender)
    question = _question(tender, "EXP-001")

    service.skip(question)

    assert question.status == QuestionStatus.skipped and question.requirement.status == S.A_VERIFIER
    assert service.generate(tender) == []  # une question ignorée n'est pas reposée
    assert db.scalar(select(AuditLog).where(AuditLog.action == "question.skipped")) is not None
    service.answer(question, "Oui, deux références de 4 000 points")  # on peut encore y répondre
    assert question.status == QuestionStatus.answered and question.requirement.status == S.CONFORME


def test_generate_questions_job(db, run_jobs_inline, fake_llm, company, tender):
    job = JobService.enqueue(
        db, "generate_questions", entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )
    db.refresh(job)
    assert job.status == JobStatus.done, job.error
    assert job.result == {"created": 2, "open": 2} and job.message == "2 questions à traiter (2 nouvelles)"
    assert len(tender.questions) == 2


def test_eligibility_job_generates_questions_after_evaluating(db, run_jobs_inline, fake_llm, company, tender):
    job = JobService.enqueue(
        db, "evaluate_eligibility", entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )
    db.refresh(job)
    assert job.status == JobStatus.done, job.error
    # les règles rejugent : ISO 14001 valide au profil ⇒ CONFORME ; CNSS absente ; 2 références ⇒ 1 projet
    assert job.result["questions"] == 2 and "2 questions" in (job.message or "")
    assert {q.requirement.code for q in tender.questions} == {"ADM-001", "EXP-001"}
