from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.workers.tasks  # noqa: F401 — enregistre les tâches dans REGISTRY
from app.models.job import Job
from app.workers.celery_app import celery_app


def _send_to_celery(job: Job, kwargs: dict) -> None:
    celery_app.send_task(f"tender_ai.{job.type}", args=[str(job.id)], kwargs=kwargs)


class JobService:
    # Point d'injection : les tests remplacent `dispatcher` pour exécuter les tâches en ligne.
    dispatcher = staticmethod(_send_to_celery)

    @classmethod
    def enqueue(
        cls, db: Session, job_type: str, *, entity_kind: str | None, entity_id: UUID | None, **kwargs
    ) -> Job:
        job = Job(type=job_type, entity_kind=entity_kind, entity_id=entity_id, params=kwargs)
        db.add(job)
        db.commit()  # le worker doit voir la ligne avant de recevoir le message
        cls.dispatcher(job, kwargs)
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
