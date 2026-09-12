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

from app.connectors.storage.base import StorageProvider
from app.connectors.storage.local import LocalStorage
from app.connectors.storage.s3 import S3Storage
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import COOKIE_NAME, UnauthorizedError
from app.core.security import decode_access_token
from app.models import User
from app.repositories import users as users_repo

__all__ = ["COOKIE_NAME", "get_current_user", "get_storage"]

_storage_override: StorageProvider | None = None


@lru_cache
def _default_storage() -> StorageProvider:
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage(s)
    return LocalStorage(Path(s.storage_local_dir))


def get_storage() -> StorageProvider:
    """Choisi par STORAGE_BACKEND ; remplaçable par les tests via `_storage_override`."""
    return _storage_override or _default_storage()


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
