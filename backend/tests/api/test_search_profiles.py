from sqlalchemy import select

from app.models import AuditLog, SearchProfile

URL = "/api/v1/search-profiles"


def test_create_list_update_delete_profile(auth_client, db):
    r = auth_client.post(
        URL,
        json={
            "name": "IT Maroc",
            "keywords": [" SI ", "ERP", "SI"],
            "sectors": ["IT"],
            "countries": ["ma"],
            "budget_min": 100000,
            "currency": "mad",
            "deadline_min_days": 7,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["keywords"] == ["SI", "ERP"] and body["countries"] == ["MA"] and body["currency"] == "MAD"
    assert body["is_active"] is True and body["last_run_at"] is None and body["regions"] == []
    pid = body["id"]

    listed = auth_client.get(URL).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == pid

    r = auth_client.patch(f"{URL}/{pid}", json={"is_active": False, "sectors": ["Énergie", "Eau"]})
    assert (
        r.status_code == 200 and r.json()["is_active"] is False and r.json()["sectors"] == ["Énergie", "Eau"]
    )
    assert db.scalar(select(AuditLog).where(AuditLog.action == "search_profile.updated")) is not None

    assert auth_client.delete(f"{URL}/{pid}").status_code == 204
    assert db.get(SearchProfile, pid) is None
    assert auth_client.get(f"{URL}/{pid}").status_code == 404


def test_profile_validation(auth_client):
    assert auth_client.post(URL, json={"keywords": ["x"]}).status_code == 422  # nom requis
    assert auth_client.post(URL, json={"name": "x", "countries": ["Maroc"]}).status_code == 422  # code ISO
    assert auth_client.post(URL, json={"name": "x", "deadline_min_days": -1}).status_code == 422


def test_profiles_require_auth(client):
    assert client.get(URL).status_code == 401
