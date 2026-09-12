from fastapi import APIRouter, Depends, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import COOKIE_NAME, get_current_user
from app.models import User
from app.schemas.auth import LoginIn, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth")
# Désactivé en test (compteur en mémoire partagé entre tous les tests) ; réactivé ponctuellement
# par les tests de sécurité de la Phase 12 via `limiter.enabled = True`.
limiter = Limiter(key_func=get_remote_address, enabled=not get_settings().is_test)


@router.post("/login", response_model=UserOut)
@limiter.limit("5/minute")
def login(request: Request, response: Response, body: LoginIn, db: Session = Depends(get_db)):
    user, token = auth_service.authenticate(db, body.email, body.password)
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        max_age=s.access_token_minutes * 60,
        path="/",
    )
    return user


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
