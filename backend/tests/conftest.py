import os

# Variables d'environnement de test — posées AVANT tout import de l'application.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-0123456789")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://tender:tender@localhost:5432/tender_test"),
)
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
