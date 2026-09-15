# Importer chaque module de tâches ici : cela remplit REGISTRY (exécution en ligne dans les tests)
# et complète `celery_app.include` côté worker.
from app.workers.tasks import demo, scheduled, search

__all__ = ["demo", "scheduled", "search"]
