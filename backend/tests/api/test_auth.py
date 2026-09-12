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
