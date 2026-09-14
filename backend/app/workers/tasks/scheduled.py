"""Tâches planifiées par Celery beat (voir `beat_schedule` dans celery_app.py).

Elles sont courtes et idempotentes : pas de `Job` de suivi (contrairement aux `tracked_task`).
Règle d'import : les tâches importent les services, jamais l'inverse.
"""

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.documents import refresh_expiry_statuses
from app.workers.celery_app import celery_app

log = get_logger("scheduled")


@celery_app.task(name="tender_ai.scheduled.refresh_document_expiry")
def refresh_document_expiry() -> int:
    """RB-007 : passe `valid → expired` les documents dont la date d'expiration est dépassée.
    Renvoie le nombre de documents modifiés."""
    with SessionLocal() as db:
        count = refresh_expiry_statuses(db)
        db.commit()
    log.info("scheduled.refresh_document_expiry", expired=count)
    return count
