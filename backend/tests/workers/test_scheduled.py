"""Tâches beat `refresh_document_expiry` (RB-007) et `refresh_tender_deadlines` (RB-002) :
enregistrement, planification, effet en base."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

from app.models import Tender, Urgency
from app.models.document import DocumentCategory, DocumentStatus
from app.services.documents import DocumentService
from app.workers.celery_app import celery_app
from app.workers.tasks import scheduled

TASK = "tender_ai.scheduled.refresh_document_expiry"
DEADLINES_TASK = "tender_ai.scheduled.refresh_tender_deadlines"


def test_task_registered_and_scheduled_daily():
    assert "app.workers.tasks.scheduled" in celery_app.conf.include
    assert TASK in celery_app.tasks
    entry = celery_app.conf.beat_schedule["refresh-document-expiry"]
    assert entry["task"] == TASK
    assert entry["schedule"].hour == {1} and entry["schedule"].minute == {0}  # 01:00 UTC chaque jour


def test_deadlines_task_registered_and_scheduled_daily_at_two():
    assert DEADLINES_TASK in celery_app.tasks
    entry = celery_app.conf.beat_schedule["refresh-tender-deadlines"]
    assert entry["task"] == DEADLINES_TASK
    assert entry["schedule"].hour == {2} and entry["schedule"].minute == {0}  # 02:00 UTC chaque jour


def test_refresh_tender_deadlines_task_expires_and_reports(db, monkeypatch):
    expired = Tender(title="Passé", deadline_at=datetime.now(UTC) - timedelta(days=2))
    soon = Tender(title="Bientôt", deadline_at=datetime.now(UTC) + timedelta(days=1))
    db.add_all([expired, soon])
    db.flush()

    @contextmanager
    def _test_session():
        yield db

    monkeypatch.setattr(scheduled, "SessionLocal", _test_session)
    assert scheduled.refresh_tender_deadlines() == {"expired": 1, "updated": 1}
    db.refresh(expired)
    db.refresh(soon)
    assert expired.is_active is False and soon.urgency == Urgency.critical


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
