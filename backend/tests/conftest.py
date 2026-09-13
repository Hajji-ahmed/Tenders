import os

# Variables d'environnement de test — posées AVANT tout import de l'application.
# DATABASE_URL est FORCÉE (pas setdefault) : une URL de dev présente dans l'environnement ne doit
# jamais atteindre la fixture `engine`, qui fait drop_all.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://tender:tender@localhost:5433/tender_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-0123456789")
os.environ.setdefault("STORAGE_BACKEND", "local")

from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.core.deps as deps  # noqa: E402
from app.connectors.storage.local import LocalStorage  # noqa: E402
from app.core.db import get_db, make_engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Certification,
    CertificationCategory,
    Company,
    CompanyProfile,
    Project,
    Technology,
    TechnologyCategory,
    User,
)

TEST_DB_LOCK_ID = 424242  # verrou consultatif : une seule session pytest à la fois sur tender_test


@pytest.fixture(scope="session")
def engine():
    """Schéma recréé une fois par session de test — uniquement sur une base dont le nom finit par _test.

    Le verrou PostgreSQL est tenu pendant toute la session : deux runs concurrents (deux terminaux,
    un agent, la CI locale…) se sérialisent au lieu de se détruire mutuellement les tables.
    """
    url = os.environ["DATABASE_URL"]
    assert (make_url(url).database or "").endswith("_test"), f"Refus de drop_all hors base *_test : {url}"
    eng = make_engine(url)
    lock_conn = eng.connect()
    lock_conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": TEST_DB_LOCK_ID})
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": TEST_DB_LOCK_ID})
    lock_conn.close()
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
    """Stockage local isolé par test, vu par FastAPI comme par les workers (via deps._storage_override)."""
    st = LocalStorage(tmp_path / "storage")
    monkeypatch.setattr(deps, "_storage_override", st)
    return st


@pytest.fixture
def app(db, storage):
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
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
def company(db) -> Company:
    """Entreprise exemple du projet, « InnoSustain » : 3 technologies, 1 certification valide,
    1 expirée, 2 projets. C'est l'entreprise unique que `CompanyService.get_or_create` renvoie."""
    today = date.today()
    c = Company(
        legal_name="Innovative & Sustainable Solutions",
        trade_name="InnoSustain",
        country="MA",
        city="Casablanca",
        sectors=["Environnement", "Énergie", "Conseil"],
        profile=CompanyProfile(
            positioning="Cabinet de conseil en transition énergétique et environnementale au Maroc"
        ),
        technologies=[
            Technology(name="Python", category=TechnologyCategory.language),
            Technology(name="PostgreSQL", category=TechnologyCategory.database),
            Technology(name="Power BI", category=TechnologyCategory.tool),
        ],
        certifications=[
            Certification(
                name="ISO 14001",
                category=CertificationCategory.qualite,
                expires_at=today + timedelta(days=365),
            ),
            Certification(
                name="ISO 9001", category=CertificationCategory.qualite, expires_at=today - timedelta(days=30)
            ),
        ],
        projects=[
            Project(title="Audit énergétique", client="Office National X", sector="Énergie"),
            Project(title="Plan climat territorial", client="Ville Y", sector="Environnement"),
        ],
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def run_jobs_inline(db, monkeypatch):
    """Exécute immédiatement les jobs enfilés, avec la session de test (pas de Celery/Redis).

    `run_job` commite : avec la session en `create_savepoint`, cela ne commite que le savepoint ;
    la transaction externe est toujours annulée à la fin du test.
    """
    import app.workers.tasks  # noqa: F401 — remplit REGISTRY (les services n'importent jamais les tâches)
    from app.services.jobs import JobService
    from app.workers.tracking import REGISTRY, run_job

    def _dispatch(job, kwargs):
        run_job(db, job, REGISTRY[job.type], **kwargs)

    monkeypatch.setattr(JobService, "dispatcher", staticmethod(_dispatch))
