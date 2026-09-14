"""Tâche beat `refresh_document_expiry` (RB-007) : enregistrement, planification, effet en base."""

from contextlib import contextmanager
from datetime import date, timedelta

from app.models.document import DocumentCategory, DocumentStatus
from app.services.documents import DocumentService
from app.workers.celery_app import celery_app
from app.workers.tasks import scheduled

TASK = "tender_ai.scheduled.refresh_document_expiry"


def test_task_registered_and_scheduled_daily():
    assert "app.workers.tasks.scheduled" in celery_app.conf.include
    assert TASK in celery_app.tasks
    entry = celery_app.conf.beat_schedule["refresh-document-expiry"]
    assert entry["task"] == TASK
    assert entry["schedule"].hour == {1} and entry["schedule"].minute == {0}  # 01:00 UTC chaque jour


def test_refresh_document_expiry_marks_expired_documents(db, company, storage, monkeypatch):
    svc = DocumentService(db, storage)
    expired = svc.upload(
        filename="cnss.pdf",
        data=b"%PDF-1.4 cnss",
        content_type="application/pdf",
        category=DocumentCategory.attestation,
        expires_at=date.today() - timedelta(days=1),
    )
    valid = svc.upload(
        filename="fiscale.pdf",
        data=b"%PDF-1.4 fiscale",
        content_type="application/pdf",
        category=DocumentCategory.attestation,
        expires_at=date.today() + timedelta(days=30),
    )
    db.flush()

    @contextmanager
    def _test_session():  # remplace SessionLocal : la session de test, jamais fermée par la tâche
        yield db

    monkeypatch.setattr(scheduled, "SessionLocal", _test_session)
    assert scheduled.refresh_document_expiry() == 1  # appel direct : exécution locale, sans broker
    db.refresh(expired)
    db.refresh(valid)
    assert expired.status == DocumentStatus.expired
    assert valid.status == DocumentStatus.valid
    assert scheduled.refresh_document_expiry() == 0  # idempotente
