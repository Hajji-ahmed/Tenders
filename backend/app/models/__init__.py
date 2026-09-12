# Importer ici CHAQUE modèle pour qu'Alembic les voie lors de l'autogénération.
from app.models.base import Base
from app.models.user import User

__all__ = ["Base", "User"]
