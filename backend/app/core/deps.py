import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.models import User
from app.repositories import users as users_repo

COOKIE_NAME = "access_token"


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
