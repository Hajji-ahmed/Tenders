"""Couche IA du score (Task 5.3) : ajustement borné, repli RB-004, passage à A_ANALYSER, job
`calculate_match_score` et enfilement automatique après une recherche."""

from sqlalchemy import func, select

from app.ai.llm import FakeLLM
from app.ai.outputs import ScoreAssessment, TenderCandidate
from app.models import AuditLog, Job, JobStatus, Tender, TenderScore, TenderStatus
from app.services.jobs import JobService
from app.services.score_service import ScoreService
from app.services.scoring import compute_score
from tests.factories import page, result


def _tender(db, **over) -> Tender:
    base = dict(
        title="Audit énergétique de douze bâtiments communaux",
        description="Diagnostic des consommations et plan d'actions.",
        organization="Commune de Rabat",
        sector="Énergie",
        country="MA",
        extra={"technologies": ["Python"], "required_certifications": ["ISO 14001"]},
    )
    base.update(over)
    t = Tender(**base)
    db.add(t)
    db.flush()
    return t


def _assessment(adjustment: int = 5) -> ScoreAssessment:
    return ScoreAssessment(
        justification="Bonne adéquation sectorielle et références solides.",
        strengths=["Secteur Énergie", "Certification ISO 14001 valide"],
        weaknesses=["Peu de références similaires"],
        adjustment=adjustment,
        adjustment_reason="références directement comparables",
    )


def test_score_tender_applies_bounded_ai_adjustment_and_audits(db, company):
    tender = _tender(db)
    llm = FakeLLM([_assessment(5)])
    deterministic = compute_score(tender, company, None, None)

    score = ScoreService(db, llm).score_tender(tender)

    assert score.tender_id == tender.id and tender.score is score
    assert float(score.total) == deterministic.total + 5 and score.ai_adjustment == 5
    assert score.justification == "Bonne adéquation sectorielle et références solides."
    assert score.strengths == ["Secteur Énergie", "Certification ISO 14001 valide"]
    assert score.weaknesses == ["Peu de références similaires"]
    assert len(score.breakdown) == 8 and score.breakdown[0]["key"] == "sector"
    assert score.scoring_version == "1.0" and score.prompt_version == "v1" and score.model
    prompt = llm.calls[0]["user"]
    assert (
        "Audit énergétique de douze bâtiments" in prompt and "InnoSustain" in prompt and "ISO 9001" in prompt
    )
    assert llm.calls[0]["tier"] == "fast"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.scored"))
    assert audit is not None and audit.entity_id == tender.id and audit.payload["total"] == float(score.total)


def test_llm_failure_keeps_deterministic_score_with_fallback_justification(db, company):
    tender = _tender(db)
    deterministic = compute_score(tender, company, None, None)

    score = ScoreService(db, FakeLLM()).score_tender(tender)  # aucune réponse scriptée : le LLM lève

    assert float(score.total) == deterministic.total and score.ai_adjustment == 0
    assert score.justification.startswith("Justification IA indisponible : ")
    assert "Secteur 100/100" in score.justification and "Éligibilité 50/100" in score.justification
    assert score.model is None and score.prompt_version is None
    assert score.strengths == ["Secteur", "Technologies", "Pays", "Certifications"]  # libellés déterministes


def test_tender_at_or_above_threshold_moves_to_a_analyser_with_history(db, company):
    high = _tender(db)  # 67,5 déterministe + 5 = 72,5 ≥ 70
    ScoreService(db, FakeLLM([_assessment(5)])).score_tender(high)
    assert high.status == TenderStatus.A_ANALYSER
    assert [(h.from_status, h.to_status) for h in high.status_history] == [
        (TenderStatus.NOUVEAU, TenderStatus.A_ANALYSER)
    ]
    assert high.status_history[0].changed_by is None and "72.5" in (high.status_history[0].comment or "")

    low = _tender(db, title="Fourniture de véhicules", sector="Transport", country="FR", extra={})
    ScoreService(db, FakeLLM([_assessment(0)])).score_tender(low)
    assert low.status == TenderStatus.NOUVEAU and low.status_history == []

    # Un statut déjà avancé n'est jamais ramené en arrière par un nouveau calcul.
    decided = _tender(db, status=TenderStatus.GO)
    ScoreService(db, FakeLLM([_assessment(5)])).score_tender(decided)
    assert decided.status == TenderStatus.GO


def test_rescoring_overwrites_the_single_score_row(db, company):
    tender = _tender(db)
    service = ScoreService(db, FakeLLM([_assessment(5), _assessment(-3)]))
    first = service.score_tender(tender)
    second = service.score_tender(tender)
    assert first.id == second.id and second.ai_adjustment == -3
    assert db.scalar(select(func.count(TenderScore.id))) == 1


def test_calculate_match_score_job(db, run_jobs_inline, company, monkeypatch):
    from app.core import deps

    monkeypatch.setattr(deps, "_llm_override", FakeLLM([_assessment(2)]))
    tender = _tender(db)

    job = JobService.enqueue(
        db, "calculate_match_score", entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )
    db.refresh(job)
    assert job.status == JobStatus.done, job.error
    assert job.result["total"] == float(tender.score.total) and job.result["adjustment"] == 2

    import uuid

    missing = JobService.enqueue(
        db, "calculate_match_score", entity_kind="tender", entity_id=None, tender_id=str(uuid.uuid4())
    )
    db.refresh(missing)
    assert missing.status == JobStatus.failed and "introuvable" in (missing.error or "")


def test_search_job_enqueues_scoring_for_created_and_merged_tenders(
    db,
    run_jobs_inline,
    company,
    search_profile,
    two_sources,
    fake_search,
    fake_crawler,
    fake_extractor,
    fake_rss,
):
    fake_search.results["*"] = [result("https://ok/ao1", "AO 1")]
    fake_crawler.pages["https://ok/ao1"] = page("https://ok/ao1", text="AO")
    fake_extractor.mapping["https://ok/ao1"] = TenderCandidate(
        is_tender=True,
        confidence=0.9,
        title="AO 1",
        organization="Org",
        sector="Énergie",
        source_url="https://ok/ao1",
    )
    fake_rss.feeds["https://feed/rss"] = [result("https://feed/ao/2", "AO 2")]
    fake_crawler.pages["https://feed/ao/2"] = page("https://feed/ao/2", text="AO")
    fake_extractor.mapping["https://feed/ao/2"] = TenderCandidate(
        is_tender=True,
        confidence=0.9,
        title="AO 1",
        organization="Org",
        sector="Énergie",
        source_url="https://feed/ao/2",
    )  # doublon : même organisme, même titre ⇒ fusionné dans la première fiche

    job = JobService.enqueue(
        db,
        "search_tenders",
        entity_kind="search_profile",
        entity_id=search_profile.id,
        search_profile_id=str(search_profile.id),
    )
    db.refresh(job)
    assert job.status == JobStatus.done, job.error
    assert job.result["created"] == 1 and job.result["merged"] == 1

    scoring_jobs = list(db.scalars(select(Job).where(Job.type == "calculate_match_score")))
    assert len(scoring_jobs) == 1  # une seule fiche ⇒ un seul calcul, même après fusion
    tender = db.scalar(select(Tender))
    assert scoring_jobs[0].entity_id == tender.id and scoring_jobs[0].status == JobStatus.done
    assert tender.score is not None and tender.score.justification.startswith("Justification IA indisponible")
    assert job.result["scoring_jobs"] == 1
