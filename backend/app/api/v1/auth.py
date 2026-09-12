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


def client_ip(request: Request) -> str:
    """IP réelle du client derrière le relais Next.js (X-Forwarded-For), sinon IP du pair TCP.

    Sans cela, toutes les requêtes relayées partagent l'IP du serveur Next.js et un visiteur
    anonyme pourrait épuiser le quota de connexion du seul utilisateur.
    """
    s = get_settings()
    peer = get_remote_address(request)
    forwarded = request.headers.get("x-forwarded-for", "")
    trusted = s.trusted_proxy_ips == "*" or peer in {ip.strip() for ip in s.trusted_proxy_ips.split(",")}
    if forwarded and trusted:
        return forwarded.split(",")[0].strip() or peer
    return peer


_settings = get_settings()
# Désactivé en test (compteur partagé entre tous les tests) ; les tests de sécurité l'activent
# ponctuellement via `limiter.enabled = True`. Compteur dans Redis hors test : partagé entre réplicas.
limiter = Limiter(
    key_func=client_ip,
    enabled=not _settings.is_test,
    storage_uri=None if _settings.is_test else _settings.redis_url,
)


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
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
