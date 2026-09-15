from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    DownloadStatus,
    ExtractionStatus,
    SearchProfile,
    SourceKind,
    Tender,
    TenderDocument,
    TenderSource,
    TenderSourceLink,
    TenderStatus,
    Urgency,
)


def _deadline(days: int) -> datetime:
    """Échéance à midi UTC dans `days` jours : insensible au fuseau de la machine de test."""
    return datetime.combine(date.today() + timedelta(days=days), time(12, 0), tzinfo=UTC)


def test_tender_defaults_and_days_left(db):
    t = Tender(title="Refonte du SI", deadline_at=_deadline(5))
    db.add(t)
    db.flush()
    assert t.status == TenderStatus.NOUVEAU
    assert t.urgency == Urgency.none
    assert t.is_active is True
    assert t.extra == {}
    assert t.days_left == 5
    assert Tender(title="sans échéance").days_left is None
    assert Tender(title="dépassé", deadline_at=_deadline(-2)).days_left == -2


def test_source_link_url_is_unique(db):
    t = Tender(title="AO 1")
    db.add(t)
    db.flush()
    db.add(TenderSourceLink(tender_id=t.id, url="https://portail.ma/ao/1"))
    db.flush()
    db.add(TenderSourceLink(tender_id=t.id, url="https://portail.ma/ao/1"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_search_profile_and_source_defaults(db):
    p = SearchProfile(name="IT Maroc", keywords=["SI", "ERP"], countries=["MA"])
    s = TenderSource(
        name="Marchés publics", kind=SourceKind.portal, base_url="https://www.marchespublics.gov.ma"
    )
    db.add_all([p, s])
    db.flush()
    assert p.is_active is True and p.sectors == [] and p.last_run_at is None
    assert s.is_enabled is True and s.priority == 100 and s.config == {} and s.last_status is None


def test_tender_cascades_links_and_documents(db):
    p = SearchProfile(name="p")
    s = TenderSource(name="rss", kind=SourceKind.rss, base_url="https://feed/rss")
    db.add_all([p, s])
    db.flush()
    t = Tender(title="AO 2", search_profile_id=p.id)
    db.add(t)
    db.flush()
    t.source_links.append(TenderSourceLink(source_id=s.id, url="https://feed/ao/2", title_seen="AO 2"))
    t.documents.append(TenderDocument(name="DCE.pdf", source_url="https://feed/ao/2/dce.pdf"))
    db.flush()
    doc = t.documents[0]
    assert doc.download_status == DownloadStatus.pending
    assert doc.extraction_status == ExtractionStatus.pending

    db.delete(t)
    db.flush()
    assert db.scalar(select(TenderSourceLink).where(TenderSourceLink.url == "https://feed/ao/2")) is None
    assert db.scalar(select(TenderDocument).where(TenderDocument.name == "DCE.pdf")) is None
    # Le profil et la source survivent à la suppression de l'opportunité.
    assert db.get(SearchProfile, p.id) is not None and db.get(TenderSource, s.id) is not None


def test_tender_embedding_column_stores_a_vector(db):
    t = Tender(title="AO vecteur", embedding=[0.0] * 1535 + [1.0])
    db.add(t)
    db.flush()
    db.expire(t)
    assert len(list(t.embedding)) == 1536 and float(t.embedding[-1]) == 1.0
