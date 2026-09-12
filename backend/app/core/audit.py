import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    entity_kind: str,
    entity_id: uuid.UUID | None,
    payload: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> AuditLog:
    """Ajoute une entrée d'historique à la session courante (commitée avec la requête)."""
    log = AuditLog(
        action=action, entity_kind=entity_kind, entity_id=entity_id, payload=payload, user_id=user_id
    )
    db.add(log)
    return log
