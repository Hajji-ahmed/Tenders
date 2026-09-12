from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models import User
from app.repositories import users as users_repo


def authenticate(db: Session, email: str, password: str) -> tuple[User, str]:
    """Vérifie les identifiants et renvoie (utilisateur, token). Même erreur pour email inconnu
    et mot de passe faux : on ne révèle pas quels comptes existent."""
    user = users_repo.get_by_email(db, email)
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Email ou mot de passe invalide", code="invalid_credentials")
    user.last_login_at = datetime.now(UTC)
    return user, create_access_token(str(user.id))
