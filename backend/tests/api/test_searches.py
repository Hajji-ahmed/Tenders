import uuid

from sqlalchemy import func, select

from app.ai.outputs import TenderCandidate
from app.models import Job, Tender
from tests.factories import page, result

URL = "/api/v1/searches"


def test_launch_search_returns_202_job(auth_client, db, search_profile):
    r = auth_client.post(URL, json={"search_profile_id": str(search_profile.id)})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["type"] == "search_tenders" and body["status"] == "pending"
    assert body["entity_kind"] == "search_profile" and body["entity_id"] == str(search_profile.id)
    job = db.get(Job, uuid.UUID(body["id"]))
    assert job.params == {"search_profile_id": str(search_profile.id)}


def test_launch_search_creates_tenders_when_run(
    auth_client,
    db,
    run_jobs_inline,
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
        is_tender=True, confidence=0.9, title="AO 1", source_url="https://ok/ao1"
    )
    fake_rss.feeds["https://feed/rss"] = []

    r = auth_client.post(URL, json={"search_profile_id": str(search_profile.id)})
    assert r.status_code == 202
    body = auth_client.get(f"/api/v1/jobs/{r.json()['id']}").json()
    assert body["status"] == "done" and body["result"]["created"] == 1
    assert db.scalar(select(func.count(Tender.id))) == 1

    listed = auth_client.get(URL).json()
    assert listed[0]["id"] == r.json()["id"] and listed[0]["type"] == "search_tenders"


def test_launch_search_unknown_profile_is_404(auth_client):
    r = auth_client.post(URL, json={"search_profile_id": str(uuid.uuid4())})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_launch_search_inactive_profile_is_422(auth_client, db, search_profile):
    search_profile.is_active = False
    db.flush()
    r = auth_client.post(URL, json={"search_profile_id": str(search_profile.id)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "profile_inactive"
