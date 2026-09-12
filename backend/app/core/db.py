import json
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _json_dumps(value) -> str:
    # Les colonnes JSON acceptent UUID, datetime, Decimal… (sérialisés en chaîne) au lieu de lever TypeError.
    return json.dumps(value, default=str, ensure_ascii=False)


def make_engine(url: str) -> Engine:
    """Moteur configuré de façon identique pour l'application et les tests."""
    return create_engine(url, pool_pre_ping=True, json_serializer=_json_dumps)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI : une session par requête, commit si succès, rollback sinon."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
