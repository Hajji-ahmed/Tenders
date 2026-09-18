import os
from pathlib import Path

# Variables d'environnement de test — posées AVANT tout import de l'application.
# DATABASE_URL est FORCÉE (pas setdefault) : une URL de dev présente dans l'environnement ne doit
# jamais atteindre la fixture `engine`, qui fait drop_all.
# 127.0.0.1 et non localhost : Docker n'écoute qu'en IPv4 et la tentative IPv6 (::1) bloque ~200 s
# sous Windows avant de se rabattre sur IPv4 (chaque session pytest durait 5 min au lieu de 1).
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_test"
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
from app.ai.embeddings import FakeEmbeddings  # noqa: E402
from app.ai.llm import FakeLLM  # noqa: E402
from app.connectors.crawl.fake import FakeCrawler  # noqa: E402
from app.connectors.extractor import FakeTenderExtractor  # noqa: E402
from app.connectors.rss import FakeRss  # noqa: E402
from app.connectors.search.fake import FakeWebSearch  # noqa: E402
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
    SearchProfile,
    SourceKind,
    Technology,
    TechnologyCategory,
    TenderSource,
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


# Fournisseurs externes simulés, injectés via deps._<nom>_override : les services et les tâches les
# obtiennent par deps.get_web_search() / get_crawler() / get_llm() / get_tender_extractor().


@pytest.fixture
def fake_search(monkeypatch) -> FakeWebSearch:
    fake = FakeWebSearch()
    monkeypatch.setattr(deps, "_web_search_override", fake)
    return fake


@pytest.fixture
def fake_crawler(monkeypatch) -> FakeCrawler:
    fake = FakeCrawler()
    monkeypatch.setattr(deps, "_crawler_override", fake)
    return fake


@pytest.fixture
def fake_llm(monkeypatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(deps, "_llm_override", fake)
    return fake


@pytest.fixture
def fake_extractor(monkeypatch) -> FakeTenderExtractor:
    fake = FakeTenderExtractor()
    monkeypatch.setattr(deps, "_tender_extractor_override", fake)
    return fake


@pytest.fixture
def fake_embeddings(monkeypatch) -> FakeEmbeddings:
    fake = FakeEmbeddings()
    monkeypatch.setattr(deps, "_embeddings_override", fake)
    return fake


@pytest.fixture
def fake_rss(monkeypatch) -> FakeRss:
    fake = FakeRss()
    monkeypatch.setattr(deps, "_rss_override", fake)
    return fake


@pytest.fixture
def search_profile(db) -> SearchProfile:
    """Profil « IT Maroc » : mots-clés SI/ERP, secteur IT, pays MA."""
    p = SearchProfile(name="IT Maroc", keywords=["SI", "ERP"], sectors=["IT"], countries=["MA"])
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def two_sources(db) -> list[TenderSource]:
    """Un moteur de recherche (sans restriction de domaine) et un flux RSS."""
    sources = [
        TenderSource(
            name="Tavily", kind=SourceKind.search_engine, config={"include_domains": []}, priority=10
        ),
        TenderSource(name="Flux portail", kind=SourceKind.rss, base_url="https://feed/rss", priority=20),
    ]
    db.add_all(sources)
    db.flush()
    return sources


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


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Fichiers d'exemple sample.{pdf,docx,xlsx,txt,zip} (générés par tests/fixtures/make_fixtures.py)."""
    return FIXTURES_DIR
