from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.api.v1 import auth as auth_module
from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.services import auth as auth_service

LOGIN = "/api/v1/auth/login"


def test_login_sets_cookie(client, user):
    r = client.post(LOGIN, json={"email": "admin@example.com", "password": "Password123!"})
    assert r.status_code == 200
    assert "access_token" in r.cookies
    assert r.json()["email"] == "admin@example.com"


def test_login_wrong_password(client, user):
    r = client.post(LOGIN, json={"email": "admin@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_same_error(client):
    r = client.post(LOGIN, json={"email": "ghost@example.com", "password": "whatever"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_still_hashes(db, monkeypatch):
    """Anti-énumération par timing : argon2 est exécuté même si l'utilisateur n'existe pas."""
    calls = []
    monkeypatch.setattr(auth_service, "verify_password", lambda p, h: calls.append(h) or False)
    with pytest.raises(UnauthorizedError):
        auth_service.authenticate(db, "ghost@example.com", "whatever")
    assert len(calls) == 1


def test_login_inactive_user_rejected(client, user, db):
    user.is_active = False
    db.flush()
    r = client.post(LOGIN, json={"email": "admin@example.com", "password": "Password123!"})
    assert r.status_code == 401


def test_login_invalid_body_uses_error_envelope(client):
    r = client.post(LOGIN, json={"email": "pas-un-email", "password": "x"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error" and "email" in body["message"]


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_after_login(client, user):
    client.post(LOGIN, json={"email": "admin@example.com", "password": "Password123!"})
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "admin@example.com"


def test_logout_clears_cookie(client, user):
    client.post(LOGIN, json={"email": "admin@example.com", "password": "Password123!"})
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invalid_cookie_is_deleted_on_401(client):
    """Cookie présent mais token rejeté : le 401 efface le cookie (sinon boucle /login ⇄ /dashboard)."""
    client.cookies.set("access_token", "garbage")
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    set_cookie = r.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie and ("Max-Age=0" in set_cookie or "expires=" in set_cookie.lower())


def test_token_with_non_uuid_subject_is_401_not_500(client):
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "not-a-uuid", "iat": now, "exp": now + timedelta(minutes=5)},
        get_settings().secret_key,
        algorithm="HS256",
    )
    client.cookies.set("access_token", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_rate_limit_uses_error_envelope(client, user, monkeypatch):
    monkeypatch.setattr(auth_module.limiter, "enabled", True)
    try:
        for _ in range(5):
            client.post(LOGIN, json={"email": "admin@example.com", "password": "nope"})
        r = client.post(LOGIN, json={"email": "admin@example.com", "password": "Password123!"})
    finally:
        auth_module.limiter.reset()
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


def test_rate_limit_key_prefers_forwarded_for(client, user, monkeypatch):
    """Derrière le relais Next.js, chaque visiteur a son propre compteur (X-Forwarded-For)."""
    monkeypatch.setattr(auth_module.limiter, "enabled", True)
    try:
        for _ in range(5):
            client.post(
                LOGIN, json={"email": "a@b.c", "password": "x"}, headers={"X-Forwarded-For": "203.0.113.9"}
            )
        r = client.post(
            LOGIN,
            json={"email": "admin@example.com", "password": "Password123!"},
            headers={"X-Forwarded-For": "198.51.100.7"},
        )
    finally:
        auth_module.limiter.reset()
    assert r.status_code == 200
