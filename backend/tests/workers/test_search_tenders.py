from datetime import date

from sqlalchemy import func, select

from app.ai.outputs import TenderCandidate
from app.models import AuditLog, JobStatus, Tender, TenderDocument, TenderSourceLink, TenderStatus
from app.services.jobs import JobService
from tests.factories import page, result


def _enqueue(db, profile):
    job = JobService.enqueue(
        db,
        "search_tenders",
        entity_kind="search_profile",
        entity_id=profile.id,
        search_profile_id=str(profile.id),
    )
    db.refresh(job)
    return job


def test_search_job_survives_source_failure(
    db, run_jobs_inline, search_profile, two_sources, fake_search, fake_crawler, fake_extractor, fake_rss
):
    fake_search.results["*"] = [result("https://ok/ao1", "AO 1", source_name="tavily")]
    fake_crawler.pages["https://ok/ao1"] = page(
        "https://ok/ao1", text="Appel d'offres 1", links=["https://ok/ao1/dce.pdf"]
    )
    fake_extractor.mapping["https://ok/ao1"] = TenderCandidate(
        is_tender=True,
        confidence=0.9,
        title="AO 1",
        organization="Commune de Rabat",
        country="MA",
        deadline_at=date(2026, 10, 30),
        source_url="https://ok/ao1",
        document_urls=["https://ok/ao1/dce.pdf"],
    )
    two_sources[1].base_url = "https://broken/feed"  # flux RSS inaccessible (FakeRss ne le connaît pas)
    db.flush()

    job = _enqueue(db, search_profile)

    assert job.status == JobStatus.done, job.error
    assert job.result["created"] == 1 and job.result["queries"]
    reports = job.result["sources"]
    assert reports[str(two_sources[0].id)]["status"] == "ok"
    assert reports[str(two_sources[1].id)]["status"] == "error"
    assert db.scalar(select(func.count(Tender.id))) == 1

    tender = db.scalar(select(Tender))
    assert tender.title == "AO 1" and tender.status == TenderStatus.NOUVEAU
    assert tender.organization == "Commune de Rabat" and tender.country == "MA"
    assert tender.deadline_at.date() == date(2026, 10, 30) and tender.search_profile_id == search_profile.id
    assert tender.source_url == "https://ok/ao1" and tender.raw["title"] == "AO 1"
    link = db.scalar(select(TenderSourceLink).where(TenderSourceLink.tender_id == tender.id))
    assert link.url == "https://ok/ao1" and link.source_id == two_sources[0].id and link.title_seen == "AO 1"
    doc = db.scalar(select(TenderDocument).where(TenderDocument.tender_id == tender.id))
    assert doc.source_url == "https://ok/ao1/dce.pdf" and doc.name == "dce.pdf"

    db.refresh(two_sources[0])
    db.refresh(two_sources[1])
    assert two_sources[0].last_status == "ok" and two_sources[0].last_run_at is not None
    assert two_sources[1].last_status == "error" and "broken/feed" in two_sources[1].last_error
    db.refresh(search_profile)
    assert search_profile.last_run_at is not None
    assert db.scalar(select(AuditLog).where(AuditLog.action == "search.launched")) is not None


def test_search_job_is_idempotent_on_known_urls(
    db, run_jobs_inline, search_profile, two_sources, fake_search, fake_crawler, fake_extractor, fake_rss
):
    fake_search.results["*"] = [result("https://ok/ao1", "AO 1")]
    fake_crawler.pages["https://ok/ao1"] = page("https://ok/ao1", text="AO")
    fake_extractor.mapping["https://ok/ao1"] = TenderCandidate(
        is_tender=True, confidence=0.9, title="AO 1", source_url="https://ok/ao1"
    )
    fake_rss.feeds["https://feed/rss"] = []

    first = _enqueue(db, search_profile)
    fetches_after_first = len(fake_crawler.calls)
    second = _enqueue(db, search_profile)

    assert first.result["created"] == 1
    assert second.status == JobStatus.done and second.result["created"] == 0
    assert second.result["sources"][str(two_sources[0].id)]["skipped_known"] == 1
    assert len(fake_crawler.calls) == fetches_after_first  # l'URL connue n'est pas recrawlée
    assert db.scalar(select(func.count(Tender.id))) == 1


def test_search_job_fails_on_unknown_profile(db, run_jobs_inline):
    import uuid

    job = JobService.enqueue(
        db,
        "search_tenders",
        entity_kind="search_profile",
        entity_id=None,
        search_profile_id=str(uuid.uuid4()),
    )
    db.refresh(job)
    assert job.status == JobStatus.failed and "introuvable" in (job.error or "")
