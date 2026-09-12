import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuditLog(UUIDMixin, Base):
    """Historique des actions importantes (FR-023). Convention `action` : `domaine.verbe`."""

    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_kind: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    user_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
