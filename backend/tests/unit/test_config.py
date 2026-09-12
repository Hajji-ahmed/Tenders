import pytest

from app.core.config import Settings

GOOD_KEY = "a3f1c9e2b7d4468f9a0c1e2d3b4a5f6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a"


def test_dev_accepts_placeholder_key():
    s = Settings(app_env="dev", secret_key="change-me-with-at-least-32-random-characters")
    assert s.app_env == "dev"


def test_prod_rejects_placeholder_key_and_insecure_cookie():
    with pytest.raises(ValueError) as exc:
        Settings(
            app_env="prod", secret_key="change-me-with-at-least-32-random-characters", cookie_secure=False
        )
    msg = str(exc.value)
    assert "SECRET_KEY" in msg and "COOKIE_SECURE" in msg


def test_prod_accepts_proper_config():
    s = Settings(
        app_env="prod", secret_key=GOOD_KEY, cookie_secure=True, storage_endpoint="https://r2.example.com"
    )
    assert s.is_deployed


def test_prod_requires_https_storage():
    with pytest.raises(ValueError, match="STORAGE_ENDPOINT"):
        Settings(
            app_env="staging",
            secret_key=GOOD_KEY,
            cookie_secure=True,
            storage_backend="s3",
            storage_endpoint="http://minio:9000",
        )
