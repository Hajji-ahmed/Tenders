from functools import lru_cache
from pathlib import Path

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.connectors.storage.base import StorageProvider
from app.connectors.storage.local import LocalStorage
from app.connectors.storage.s3 import S3Storage
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.models import User
from app.repositories import users as users_repo

COOKIE_NAME = "access_token"


@lru_cache
def get_storage() -> StorageProvider:
    """Choisi par STORAGE_BACKEND. Appelable depuis FastAPI (Depends) comme depuis les workers."""
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage(s)
    return LocalStorage(Path(s.storage_local_dir))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise UnauthorizedError("Authentification requise")
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError as e:
        raise UnauthorizedError("Session invalide ou expirée") from e
    user = users_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Utilisateur inconnu")
    return user
