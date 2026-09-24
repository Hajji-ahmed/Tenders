# Importer chaque module de tâches ici : cela remplit REGISTRY (exécution en ligne dans les tests)
# et complète `celery_app.include` côté worker.
from app.workers.tasks import analysis, demo, documents, eligibility, questions, scheduled, scoring, search

__all__ = ["analysis", "demo", "documents", "eligibility", "questions", "scheduled", "scoring", "search"]
