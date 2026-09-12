from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "tender_ai",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    # Chaque phase ajoute ici ses modules de tâches (côté worker ; les tests importent app.workers.tasks).
    include=["app.workers.tasks.demo"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    task_time_limit=60 * 30,
    # Échec rapide si Redis est injoignable : l'API ne doit pas rester bloquée sur un enqueue.
    broker_connection_timeout=2,
    broker_connection_retry_on_startup=True,
    task_publish_retry_policy={
        "max_retries": 2,
        "interval_start": 0,
        "interval_step": 0.5,
        "interval_max": 1,
    },
    beat_schedule={},  # rempli par les phases 2, 4 et 11
)
