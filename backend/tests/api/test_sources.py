from app.ai.outputs import TenderCandidate
from tests.factories import page, result

URL = "/api/v1/sources"


def test_create_and_toggle_source(auth_client):
    r = auth_client.post(
        URL,
        json={"name": "Portail", "kind": "rss", "base_url": "https://portail.ma/rss", "priority": 5},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "rss" and body["is_enabled"] is True and body["config"] == {}
    assert body["last_status"] is None and body["last_run_at"] is None

    r = auth_client.patch(f"{URL}/{body['id']}", json={"is_enabled": False})
    assert r.status_code == 200 and r.json()["is_enabled"] is False

    assert auth_client.get(URL).json()["total"] == 1


def test_source_validation(auth_client):
    r = auth_client.post(URL, json={"name": "Flux", "kind": "rss"})  # URL obligatoire hors moteur
    assert r.status_code == 422 and "base_url" in r.json()["error"]["message"]
    assert auth_client.post(URL, json={"name": "x", "kind": "telepathie"}).status_code == 422
    r = auth_client.post(URL, json={"name": "Tavily", "kind": "search_engine", "config": {"max_results": 5}})
    assert r.status_code == 201


def test_test_source_runs_a_limited_collection(
    auth_client, search_profile, fake_search, fake_crawler, fake_extractor, fake_rss
):
    fake_rss.feeds["https://feed/rss"] = [
        result(f"https://feed/ao/{i}", f"AO {i}", source_name="rss") for i in range(5)
    ]
    for i in range(5):
        fake_crawler.pages[f"https://feed/ao/{i}"] = page(f"https://feed/ao/{i}", text=f"AO {i}")
        fake_extractor.mapping[f"https://feed/ao/{i}"] = TenderCandidate(
            is_tender=True, confidence=0.9, title=f"AO {i}", source_url=f"https://feed/ao/{i}"
        )
    src = auth_client.post(URL, json={"name": "Flux", "kind": "rss", "base_url": "https://feed/rss"}).json()

    r = auth_client.post(f"{URL}/{src['id']}/test")
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["status"] == "ok" and report["found"] == 5 and report["fetched"] == 3  # limité à 3 URL
    assert [c["title"] for c in report["candidates"]] == ["AO 0", "AO 1", "AO 2"]
    assert len(fake_crawler.calls) == 3

    # Le test ne crée aucune opportunité et ne modifie pas la source.
    assert auth_client.get("/api/v1/tenders").json()["total"] == 0
    assert auth_client.get(f"{URL}/{src['id']}").json()["last_status"] is None


def test_test_source_reports_a_broken_feed_without_http_error(auth_client, fake_rss):
    src = auth_client.post(
        URL, json={"name": "Cassé", "kind": "rss", "base_url": "https://broken/feed"}
    ).json()
    r = auth_client.post(f"{URL}/{src['id']}/test")
    assert r.status_code == 200
    assert r.json()["status"] == "error" and "broken/feed" in r.json()["error"]


def test_test_unknown_source_is_404(auth_client):
    r = auth_client.post(f"{URL}/00000000-0000-0000-0000-000000000000/test")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
