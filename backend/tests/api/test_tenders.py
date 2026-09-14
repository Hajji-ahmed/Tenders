import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Tender, TenderDocument, TenderSourceLink, TenderStatus

URL = "/api/v1/tenders"


def _deadline(days: int) -> datetime:
    return datetime.now(tz=UTC).replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=days)


@pytest.fixture
def tenders(db, two_sources):
    rows = [
        Tender(
            title="Refonte du SI",
            organization="Commune A",
            country="MA",
            sector="IT",
            deadline_at=_deadline(10),
        ),
        Tender(
            title="Audit énergétique",
            country="SN",
            sector="Énergie",
            deadline_at=_deadline(3),
            status=TenderStatus.GO,
        ),
        Tender(title="Ancien SI", country="MA", sector="IT", is_active=False, deadline_at=_deadline(-30)),
        Tender(title="Sans échéance", description="Contient SI dans la description", country="FR"),
    ]
    # created_at explicites : `now()` PostgreSQL est identique pour toute la transaction de test.
    for i, row in enumerate(rows):
        row.created_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=i)
    rows[0].source_links.append(
        TenderSourceLink(source_id=two_sources[0].id, url="https://a/1", title_seen="SI")
    )
    rows[0].source_links.append(TenderSourceLink(source_id=two_sources[1].id, url="https://b/1"))
    rows[0].documents.append(TenderDocument(name="DCE.pdf", source_url="https://a/1/dce.pdf"))
    db.add_all(rows)
    db.flush()
    return rows


def test_list_excludes_inactive_by_default_and_orders_by_creation(auth_client, tenders):
    body = auth_client.get(URL).json()
    assert body["total"] == 3
    assert [t["title"] for t in body["items"]] == ["Sans échéance", "Audit énergétique", "Refonte du SI"]
    first = next(t for t in body["items"] if t["title"] == "Refonte du SI")
    assert first["days_left"] == 10 and first["source_count"] == 2 and first["document_count"] == 1
    assert first["score_total"] is None and first["status"] == "NOUVEAU" and first["urgency"] == "none"

    assert auth_client.get(URL, params={"active_only": "false"}).json()["total"] == 4


def test_list_filters(auth_client, tenders):
    q = lambda **params: [t["title"] for t in auth_client.get(URL, params=params).json()["items"]]  # noqa: E731
    assert q(q="SI") == ["Sans échéance", "Refonte du SI"]  # titre OU description, insensible à la casse
    assert q(country="ma") == ["Refonte du SI"]
    assert q(sector="Énergie") == ["Audit énergétique"]
    assert q(status="GO") == ["Audit énergétique"]
    assert q(deadline_before=(datetime.now(tz=UTC) + timedelta(days=5)).date().isoformat()) == [
        "Audit énergétique"
    ]
    assert q(sort="deadline") == [
        "Audit énergétique",
        "Refonte du SI",
        "Sans échéance",
    ]  # sans échéance en dernier
    assert q(sort="-deadline")[:2] == ["Refonte du SI", "Audit énergétique"]
    assert q(sort="created")[0] == "Refonte du SI"


def test_list_pagination_and_bad_sort(auth_client, tenders):
    body = auth_client.get(URL, params={"page": 2, "size": 2}).json()
    assert body["total"] == 3 and len(body["items"]) == 1 and body["page"] == 2
    assert auth_client.get(URL, params={"sort": "prix"}).status_code == 422


def test_get_tender_detail(auth_client, tenders, two_sources):
    body = auth_client.get(f"{URL}/{tenders[0].id}").json()
    assert body["title"] == "Refonte du SI" and body["organization"] == "Commune A"
    assert {link["url"] for link in body["source_links"]} == {"https://a/1", "https://b/1"}
    assert body["source_links"][0]["source_name"] in {"Tavily", "Flux portail"}
    assert body["documents"][0]["name"] == "DCE.pdf" and body["documents"][0]["download_status"] == "pending"

    assert auth_client.get(f"{URL}/{uuid.uuid4()}").status_code == 404


def test_tenders_require_auth(client):
    assert client.get(URL).status_code == 401
