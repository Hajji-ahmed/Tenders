import os

# Variables d'environnement de test — posées AVANT tout import de l'application.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-0123456789")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://tender:tender@localhost:5433/tender_test"),
)
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.connectors.storage.local import LocalStorage  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.deps import get_storage  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """Schéma recréé une fois par session de test sur la base tender_test."""
    eng = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """Session dans une transaction annulée à la fin de chaque test : base toujours propre."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Stockage local isolé par test ; injecté à la fois dans FastAPI et dans les workers."""
    import app.core.deps as deps

    st = LocalStorage(tmp_path / "storage")
    monkeypatch.setattr(deps, "get_storage", lambda: st)
    return st


@pytest.fixture
def app(db, storage):
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    application.dependency_overrides[get_storage] = lambda: storage
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def user(db):
    u = User(email="admin@example.com", password_hash=hash_password("Password123!"))
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def auth_client(client, user) -> TestClient:
    client.post("/api/v1/auth/login", json={"email": user.email, "password": "Password123!"})
    return client


@pytest.fixture
def run_jobs_inline(db, monkeypatch):
    """Exécute immédiatement les jobs enfilés, avec la session de test (pas de Celery/Redis).

    `run_job` commite : avec la session en `create_savepoint`, cela ne commite que le savepoint ;
    la transaction externe est toujours annulée à la fin du test.
    """
    from app.services.jobs import JobService
    from app.workers.tracking import REGISTRY, run_job

    def _dispatch(job, kwargs):
        run_job(db, job, REGISTRY[job.type], **kwargs)

    monkeypatch.setattr(JobService, "dispatcher", staticmethod(_dispatch))
