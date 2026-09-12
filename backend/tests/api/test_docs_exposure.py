from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_docs_hidden_outside_dev():
    """APP_ENV=test ici : comme en prod, Swagger et le schéma OpenAPI ne sont pas servis."""
    assert get_settings().app_env == "test"
    client = TestClient(create_app())
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404
