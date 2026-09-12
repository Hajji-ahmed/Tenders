from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, verify_password
from app.models import User
from app.repositories import users as users_repo


def authenticate(db: Session, email: str, password: str) -> tuple[User, str]:
    """Vérifie les identifiants et renvoie (utilisateur, token).

    Même message d'erreur et même coût (argon2 toujours exécuté) que l'email existe ou non :
    on ne révèle ni l'existence des comptes ni leur état.
    """
    user = users_repo.get_by_email(db, email)
    password_ok = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not user.is_active or not password_ok:
        raise UnauthorizedError("Email ou mot de passe invalide", code="invalid_credentials")
    user.last_login_at = datetime.now(UTC)
    return user, create_access_token(str(user.id))
