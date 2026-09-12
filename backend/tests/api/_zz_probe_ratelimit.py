"""Sonde (lecture seule sur le dépôt) : la clé du rate-limit est-elle partagée derrière un relais ?"""

from fastapi.testclient import TestClient


def test_shared_counter_behind_relay(app, user):
    from app.api.v1.auth import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        # Deux navigateurs distincts, mais le même pair TCP (le conteneur Next.js).
        attacker = TestClient(app, client=("172.18.0.5", 40001))
        victim = TestClient(app, client=("172.18.0.5", 40002))
        for _ in range(5):
            r = attacker.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrongwrong"},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
            print("attacker ->", r.status_code)
        r = victim.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "Password123!"},
            headers={"X-Forwarded-For": "198.51.100.7"},
        )
        print("victim ->", r.status_code, r.text)
        print("storage:", type(limiter._storage).__name__)
        assert r.status_code == 429
    finally:
        limiter.reset()
        limiter.enabled = False


def test_distinct_peers_are_independent(app, user):
    """Contre-épreuve : si les pairs TCP diffèrent, la victime passe."""
    from app.api.v1.auth import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        attacker = TestClient(app, client=("203.0.113.10", 40001))
        victim = TestClient(app, client=("198.51.100.7", 40002))
        for _ in range(5):
            attacker.post(
                "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrongwrong"}
            )
        r = victim.post("/api/v1/auth/login", json={"email": user.email, "password": "Password123!"})
        print("victim (distinct peer) ->", r.status_code)
        assert r.status_code == 200
    finally:
        limiter.reset()
        limiter.enabled = False
