from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger
from app.models.job import Job, JobStatus
from app.workers.celery_app import celery_app

log = get_logger("jobs")


def _send_to_celery(job: Job, kwargs: dict) -> None:
    celery_app.send_task(f"tender_ai.{job.type}", args=[str(job.id)], kwargs=kwargs)


def _no_dispatch(job: Job, kwargs: dict) -> None:
    """En test : le job reste `pending` ; la fixture `run_jobs_inline` remplace ce dispatcher
    quand un test veut réellement exécuter la tâche."""


class JobService:
    # Point d'injection : les tests remplacent `dispatcher` pour exécuter les tâches en ligne.
    dispatcher = staticmethod(_no_dispatch if get_settings().is_test else _send_to_celery)

    @classmethod
    def enqueue(
        cls, db: Session, job_type: str, *, entity_kind: str | None, entity_id: UUID | None, **kwargs
    ) -> Job:
        job = Job(type=job_type, entity_kind=entity_kind, entity_id=entity_id, params=kwargs)
        db.add(job)
        db.commit()  # le worker doit voir la ligne avant de recevoir le message
        try:
            cls.dispatcher(job, kwargs)
        except Exception as e:  # noqa: BLE001 — broker indisponible : le job ne doit pas rester `pending`
            job.status = JobStatus.failed
            job.error = f"dispatch: {type(e).__name__}: {e}"[:4000]
            job.finished_at = datetime.now(UTC)
            db.commit()
            log.exception("job.dispatch_failed", type=job.type, job_id=str(job.id))
            raise ServiceUnavailableError("File de traitement indisponible, réessayez dans un instant") from e
        return job

    @staticmethod
    def get(db: Session, job_id: UUID) -> Job | None:
        return db.get(Job, job_id)

    @staticmethod
    def list(
        db: Session, *, type: str | None = None, status: str | None = None, limit: int = 50
    ) -> list[Job]:
        q = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if type:
            q = q.where(Job.type == type)
        if status:
            q = q.where(Job.status == status)
        return list(db.scalars(q))
