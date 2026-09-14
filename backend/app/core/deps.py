"""Dépendances partagées par l'API (via Depends) et les workers (appel direct).

Convention : dans les services et les tâches, toujours écrire `from app.core import deps` puis
`deps.get_storage()` — jamais `from app.core.deps import get_storage`. Les tests remplacent les
fournisseurs via les variables `_*_override` ci-dessous (fixtures de conftest.py).
"""

from functools import lru_cache
from pathlib import Path
from uuid import UUID

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.ai.llm import FakeLLM, LLMProvider
from app.ai.openai_llm import OpenAILLM
from app.connectors.crawl.base import CrawlerProvider
from app.connectors.crawl.fake import FakeCrawler
from app.connectors.crawl.httpx_crawler import HttpxCrawler
from app.connectors.crawl.playwright_crawler import PlaywrightCrawler
from app.connectors.extractor import FakeTenderExtractor, TenderExtractor
from app.connectors.llm_extractor import LLMTenderExtractor
from app.connectors.search.base import WebSearchProvider
from app.connectors.search.fake import FakeWebSearch
from app.connectors.search.tavily import TavilySearch
from app.connectors.storage.base import StorageProvider
from app.connectors.storage.local import LocalStorage
from app.connectors.storage.s3 import S3Storage
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import COOKIE_NAME, UnauthorizedError
from app.core.security import decode_access_token
from app.models import User
from app.repositories import users as users_repo

__all__ = [
    "COOKIE_NAME",
    "get_crawler",
    "get_current_user",
    "get_js_crawler",
    "get_llm",
    "get_storage",
    "get_tender_extractor",
    "get_web_search",
]

_storage_override: StorageProvider | None = None
_web_search_override: WebSearchProvider | None = None
_crawler_override: CrawlerProvider | None = None
_llm_override: LLMProvider | None = None
_tender_extractor_override: TenderExtractor | None = None


@lru_cache
def _default_storage() -> StorageProvider:
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage(s)
    return LocalStorage(Path(s.storage_local_dir))


def get_storage() -> StorageProvider:
    """Choisi par STORAGE_BACKEND ; remplaçable par les tests via `_storage_override`."""
    return _storage_override or _default_storage()


def _not_configured(what: str, env_var: str) -> RuntimeError:
    return RuntimeError(f"Aucun fournisseur {what} configuré : renseigner {env_var} dans .env")


# En APP_ENV=test, les fournisseurs externes sont des fakes vides : aucun test ne sort sur le réseau.
# Hors test, les implémentations réelles sont construites à la demande et mises en cache.


@lru_cache
def _default_web_search() -> WebSearchProvider:
    s = get_settings()
    if s.is_test:
        return FakeWebSearch()
    if not s.tavily_api_key:
        raise _not_configured("de recherche web", "TAVILY_API_KEY")
    return TavilySearch(s.tavily_api_key)


@lru_cache
def _default_crawler() -> CrawlerProvider:
    if get_settings().is_test:
        return FakeCrawler()
    return HttpxCrawler()  # pages dynamiques : `get_js_crawler()`


@lru_cache
def _default_js_crawler() -> CrawlerProvider:
    if get_settings().is_test:
        return FakeCrawler()
    return PlaywrightCrawler()


@lru_cache
def _default_llm() -> LLMProvider:
    s = get_settings()
    if s.is_test:
        return FakeLLM()
    if not s.openai_api_key:
        raise _not_configured("LLM", "OPENAI_API_KEY")
    return OpenAILLM(s)


@lru_cache
def _default_tender_extractor() -> TenderExtractor:
    if get_settings().is_test:
        return FakeTenderExtractor()
    return LLMTenderExtractor(get_llm())


def get_web_search() -> WebSearchProvider:
    return _web_search_override or _default_web_search()


def get_crawler() -> CrawlerProvider:
    return _crawler_override or _default_crawler()


def get_js_crawler() -> CrawlerProvider:
    """Crawler Chromium pour les sources `render_js: true` ; le même override (fake) qu'en statique."""
    return _crawler_override or _default_js_crawler()


def get_llm() -> LLMProvider:
    return _llm_override or _default_llm()


def get_tender_extractor() -> TenderExtractor:
    return _tender_extractor_override or _default_tender_extractor()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise UnauthorizedError("Authentification requise")
    try:
        user_id = UUID(decode_access_token(token))
    except (jwt.PyJWTError, ValueError) as e:
        raise UnauthorizedError("Session invalide ou expirée") from e
    user = users_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Utilisateur inconnu")
    return user
