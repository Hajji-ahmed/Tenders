"""Pipeline d'ingestion v2 : normaliser → valider → dédupliquer → persister (ou fusionner)."""

from datetime import date, timedelta

from sqlalchemy import func, select

from app.ai.embeddings import FakeEmbeddings
from app.ai.outputs import TenderCandidate
from app.models import AuditLog, Tender, TenderSourceLink, TenderStatus, Urgency
from app.services.collect import SourceReport
from app.services.dedup import Deduplicator
from app.services.ingest import IngestService


def _cand(url: str, **kw) -> TenderCandidate:
    base = dict(
        is_tender=True,
        confidence=0.9,
        title="Refonte du système d'information",
        organization="Commune de Rabat",
        country="Maroc",
        deadline_at=date.today() + timedelta(days=30),
        source_url=url,
    )
    base.update(kw)
    return TenderCandidate(**base)


def _report(*candidates: TenderCandidate, source_id=None, titles: dict | None = None) -> SourceReport:
    return SourceReport(
        source_id=str(source_id) if source_id else None,
        kind="rss",
        candidates=list(candidates),
        titles=titles or {},
    )


def _service(db) -> IngestService:
    emb = FakeEmbeddings()  # 1536 dimensions, comme la colonne `embedding`
    return IngestService(db, emb, Deduplicator(db, emb))


def test_two_announcements_of_same_tender_give_one_tender_with_two_sources(db, search_profile, two_sources):
    report = _report(
        _cand("https://a/1", reference="AO 12/2026"),
        _cand("https://b/1", title="REFONTE DU SYSTEME D INFORMATION", reference="ao-12-2026"),
        source_id=two_sources[1].id,
        titles={"https://a/1": "Refonte SI", "https://b/1": "Refonte SI (bis)"},
    )

    stats = _service(db).ingest(report, search_profile)

    assert (stats.created, stats.merged, stats.skipped, stats.invalid) == (1, 1, 0, 0)
    assert db.scalar(select(func.count(Tender.id))) == 1
    tender = db.scalar(select(Tender))
    assert {(link.url, link.title_seen) for link in tender.source_links} == {
        ("https://a/1", "Refonte SI"),
        ("https://b/1", "Refonte SI (bis)"),
    }
    assert all(link.source_id == two_sources[1].id for link in tender.source_links)
    assert [d["action"] for d in stats.details] == ["created", "merged"]
    assert stats.details[1]["rule"] == "reference" and stats.details[1]["tender_id"] == str(tender.id)
    assert stats.details[0]["url"] == "https://a/1" and stats.details[0]["tender_id"] == str(tender.id)


def test_created_tender_is_normalized_vectorized_and_audited(db, search_profile):
    c = _cand("https://a/1", reference="AO 12/2026", currency="mad", description="  Mission  longue  ")

    _service(db).ingest(_report(c), search_profile)

    tender = db.scalar(select(Tender))
    assert tender.title == "Refonte du système d'information" and tender.status == TenderStatus.NOUVEAU
    assert tender.country == "MA" and tender.currency == "MAD" and tender.description == "Mission longue"
    assert tender.norm_title == "refonte du systeme d information"
    assert tender.norm_org == "commune de rabat" and tender.norm_reference == "AO122026"
    assert tender.fingerprint and len(tender.fingerprint) == 40
    assert tender.embedding is not None and len(tender.embedding) == 1536
    assert tender.is_active is True and tender.search_profile_id == search_profile.id
    assert tender.source_url == "https://a/1" and tender.raw["reference"] == "AO 12/2026"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.created"))
    assert audit is not None and audit.entity_id == tender.id and audit.payload["url"] == "https://a/1"


def test_candidate_with_past_deadline_is_created_inactive(db, search_profile):
    expired = _cand("https://a/old", deadline_at=date.today() - timedelta(days=1))
    today = _cand("https://a/today", title="Autre marché", deadline_at=date.today())

    stats = _service(db).ingest(_report(expired, today), search_profile)

    assert stats.created == 2
    by_url = {t.source_url: t for t in db.scalars(select(Tender))}
    assert by_url["https://a/old"].is_active is False and by_url["https://a/old"].urgency == Urgency.none
    assert by_url["https://a/today"].is_active is True  # échéance du jour : encore ouverte
    assert by_url["https://a/today"].urgency == Urgency.critical


def test_urgency_is_set_at_creation_and_when_a_merge_brings_the_deadline(db, search_profile):
    service = _service(db)
    stats = service.ingest(
        _report(
            _cand("https://a/soon", deadline_at=date.today() + timedelta(days=2)),
            _cand(
                "https://a/undated", title="Fourniture de mobilier", organization="Org B", deadline_at=None
            ),
        ),
        search_profile,
    )
    assert stats.created == 2
    by_url = {t.source_url: t for t in db.scalars(select(Tender))}
    assert by_url["https://a/soon"].urgency == Urgency.critical
    assert by_url["https://a/undated"].urgency == Urgency.none

    # Une seconde annonce du marché sans échéance (même organisme, même titre) apporte la date.
    stats = service.ingest(
        _report(
            _cand(
                "https://b/undated",
                title="Fourniture de mobilier",
                organization="Org B",
                deadline_at=date.today() + timedelta(days=10),
            )
        ),
        search_profile,
    )
    assert stats.merged == 1
    db.refresh(by_url["https://a/undated"])
    assert by_url["https://a/undated"].days_left == 10
    assert by_url["https://a/undated"].urgency == Urgency.medium


def test_invalid_candidates_are_counted_with_a_reason(db, search_profile):
    report = _report(
        _cand("https://x/1", is_tender=False),
        _cand("https://x/2", confidence=0.5),
        _cand("https://x/3", title="   "),
        _cand("", title="Sans URL"),
    )

    stats = _service(db).ingest(report, search_profile)

    assert stats.invalid == 4 and stats.created == 0
    assert db.scalar(select(func.count(Tender.id))) == 0
    assert [d["rule"] for d in stats.details] == ["not_tender", "low_confidence", "empty_title", "empty_url"]
    assert all(d["action"] == "invalid" for d in stats.details)


def test_already_linked_url_is_skipped_not_merged(db, search_profile):
    service = _service(db)
    service.ingest(_report(_cand("https://a/1")), search_profile)

    stats = service.ingest(_report(_cand("https://a/1", title="Titre re-extrait")), search_profile)

    assert (stats.created, stats.merged, stats.skipped) == (0, 0, 1)
    assert stats.details[0]["action"] == "skipped" and stats.details[0]["rule"] == "url"
    assert db.scalar(select(func.count(TenderSourceLink.id))) == 1
    assert db.scalar(select(Tender)).title == "Refonte du système d'information"


def test_stats_add_accumulates_counts_and_details():
    from app.services.ingest import IngestStats

    total = IngestStats()
    total.add(IngestStats(created=1, details=[{"url": "a", "action": "created", "rule": None}]))
    total.add(IngestStats(merged=2, invalid=1, details=[{"url": "b", "action": "merged", "rule": "url"}]))

    assert total.as_dict() == {"created": 1, "merged": 2, "skipped": 0, "invalid": 1}
    assert [d["url"] for d in total.details] == ["a", "b"]
