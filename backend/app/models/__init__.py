# Importer ici CHAQUE modèle pour qu'Alembic les voie lors de l'autogénération.
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.job import Job, JobStatus
from app.models.user import User

__all__ = ["AuditLog", "Base", "Job", "JobStatus", "User"]
