from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "tender_ai",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    # Chaque phase ajoute ici ses modules de tâches.
    include=["app.workers.tasks.demo"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    task_time_limit=60 * 30,
    task_always_eager=_settings.celery_task_always_eager,
    beat_schedule={},  # rempli par les phases 2, 4 et 11
)
