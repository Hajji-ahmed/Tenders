"""RB-002 : urgence selon les jours restants et rafraîchissement quotidien (expiration + urgence)."""

from datetime import UTC, datetime, time, timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import select

from app.models import Tender, Urgency
from app.services.deadlines import compute_urgency, refresh_tender_deadlines

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("days_left", "expected"),
    [
        (None, Urgency.none),
        (30, Urgency.low),
        (15, Urgency.low),
        (14, Urgency.medium),
        (8, Urgency.medium),
        (7, Urgency.high),
        (3, Urgency.high),
        (2, Urgency.critical),
        (0, Urgency.critical),
        (-1, Urgency.critical),
    ],
)
def test_compute_urgency_thresholds(days_left, expected):
    assert compute_urgency(days_left) == expected


def _deadline(days: int) -> datetime:
    """Échéance à J+days, fin de journée UTC (comme l'ingestion)."""
    return datetime.combine((NOW + timedelta(days=days)).date(), time(23, 59, 59), tzinfo=UTC)


@pytest.fixture
def tenders(db) -> dict[str, Tender]:
    rows = {
        "yesterday": Tender(title="J-1", deadline_at=_deadline(-1), urgency=Urgency.high),
        "today": Tender(title="J0", deadline_at=_deadline(0)),
        "soon": Tender(title="J+2", deadline_at=_deadline(2)),
        "mid": Tender(title="J+10", deadline_at=_deadline(10), urgency=Urgency.medium),
        "far": Tender(title="J+30", deadline_at=_deadline(30)),
        "undated": Tender(title="Sans échéance"),
        "archived": Tender(title="Déjà inactif", deadline_at=_deadline(-40), is_active=False),
    }
    db.add_all(rows.values())
    db.flush()
    return rows


@freeze_time(NOW)
def test_refresh_deactivates_expired_and_recomputes_urgency(db, tenders):
    result = refresh_tender_deadlines(db)

    for t in tenders.values():
        db.refresh(t)
    assert tenders["yesterday"].is_active is False and tenders["yesterday"].urgency == Urgency.none
    assert tenders["today"].is_active is True and tenders["today"].urgency == Urgency.critical
    assert tenders["soon"].urgency == Urgency.critical
    assert tenders["mid"].urgency == Urgency.medium  # déjà juste : non comptée
    assert tenders["far"].urgency == Urgency.low
    assert tenders["undated"].urgency == Urgency.none and tenders["undated"].is_active is True
    assert tenders["archived"].is_active is False
    assert result == {"expired": 1, "updated": 3}  # today, soon, far

    assert refresh_tender_deadlines(db) == {"expired": 0, "updated": 0}  # idempotente
    assert db.scalar(select(Tender).where(Tender.title == "J-1")).is_active is False
