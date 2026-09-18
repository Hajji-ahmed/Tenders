import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Tender, TenderSourceLink

URL = "/api/v1/tenders"


@pytest.fixture
def merged_tender(db, two_sources) -> Tender:
    """Une fiche issue de deux annonces (moteur puis flux RSS) : deux liens de provenance."""
    t = Tender(title="Refonte du SI", organization="Commune A")
    t.source_links.append(
        TenderSourceLink(
            source_id=two_sources[0].id,
            url="https://a/1",
            title_seen="Refonte SI",
            collected_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        )
    )
    t.source_links.append(
        TenderSourceLink(
            source_id=two_sources[1].id,
            url="https://b/1",
            title_seen="Refonte SI (bis)",
            collected_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC) + timedelta(hours=1),
        )
    )
    db.add(t)
    db.flush()
    return t


def test_list_sources_of_a_tender_in_collection_order(auth_client, merged_tender):
    body = auth_client.get(f"{URL}/{merged_tender.id}/sources").json()

    assert [link["url"] for link in body] == ["https://a/1", "https://b/1"]
    assert [link["source_name"] for link in body] == ["Tavily", "Flux portail"]
    assert body[1]["title_seen"] == "Refonte SI (bis)" and body[1]["collected_at"].startswith("2026-09-01T11")


def test_sources_of_unknown_tender_is_404(auth_client):
    assert auth_client.get(f"{URL}/{uuid.uuid4()}/sources").status_code == 404


def test_tender_sources_require_auth(client, merged_tender):
    assert client.get(f"{URL}/{merged_tender.id}/sources").status_code == 401
