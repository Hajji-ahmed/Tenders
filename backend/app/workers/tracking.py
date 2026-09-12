"""Suivi uniforme des tâches longues : statut, progression, erreur, durée.

Une tâche métier est une simple fonction `fn(db, job, **kwargs) -> dict`. Le décorateur
`@tracked_task("type")` l'enregistre auprès de Celery et gère le cycle de vie du `Job`.
En test, `task.run_inline(db, job, **kwargs)` exécute la fonction sans Celery.

Règle d'import : les tâches importent les services, jamais l'inverse (sinon import circulaire).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.job import Job, JobStatus
from app.workers.celery_app import celery_app

log = get_logger("jobs")

REGISTRY: dict[str, Callable] = {}  # job_type -> fn(db, job, **kwargs)


def run_job(db: Session, job: Job, fn: Callable, **kwargs) -> None:
    job.status = JobStatus.running
    job.started_at = datetime.now(UTC)
    db.commit()
    started = datetime.now(UTC)
    try:
        result = fn(db, job, **kwargs)
        job.status = JobStatus.done
        job.result = result
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        db.commit()  # dans le try : un résultat non sérialisable ou une erreur DB = échec du job
        log.info("job.done", type=job.type, job_id=str(job.id), duration_ms=_ms_since(started))
    except Exception as e:  # noqa: BLE001 — tout échec doit être journalisé, jamais avalé
        db.rollback()
        log.exception("job.failed", type=job.type, job_id=str(job.id), duration_ms=_ms_since(started))
        _mark_failed(db, job, f"{type(e).__name__}: {e}")


def _mark_failed(db: Session, job: Job, error: str) -> None:
    job.status = JobStatus.failed
    job.error = error[:4000]
    job.result = None
    job.finished_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:  # noqa: BLE001 — dernier recours : ne jamais laisser un job en `running`
        db.rollback()
        log.exception("job.mark_failed_error", type=job.type, job_id=str(job.id))
        raise


def set_progress(db: Session, job: Job, progress: int, message: str | None = None) -> None:
    job.progress = max(0, min(100, progress))
    job.message = message
    db.commit()


def tracked_task(job_type: str):
    def decorator(fn: Callable):
        REGISTRY[job_type] = fn

        @celery_app.task(bind=True, name=f"tender_ai.{job_type}")
        def _task(self, job_id: str, **kwargs):
            with SessionLocal() as db:
                job = db.get(Job, UUID(job_id))
                if job is None:
                    log.error("job.missing", type=job_type, job_id=job_id)
                    return
                job.celery_task_id = self.request.id
                run_job(db, job, fn, **kwargs)

        _task.run_inline = fn
        return _task

    return decorator


def _ms_since(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)
