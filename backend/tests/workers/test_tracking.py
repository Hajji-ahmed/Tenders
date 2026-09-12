import uuid
from datetime import UTC, datetime

import pytest

from app.core.errors import ServiceUnavailableError
from app.models.job import Job, JobStatus
from app.services.jobs import JobService
from app.workers.tracking import REGISTRY, run_job


def test_tracked_task_marks_done(db, run_jobs_inline):
    job = JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=2)
    db.refresh(job)
    assert job.status == JobStatus.done
    assert job.result == {"doubled": 4}
    assert job.progress == 100
    assert job.started_at is not None and job.finished_at is not None


def test_tracked_task_marks_failed(db, run_jobs_inline):
    job = JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=-1)
    db.refresh(job)
    assert job.status == JobStatus.failed
    assert "ValueError" in job.error
    assert job.finished_at is not None


def test_run_inline_exposes_plain_function(db):
    from app.workers.tasks.demo import demo_task

    job = Job(type="demo")
    assert demo_task.run_inline(db, job, x=5) == {"doubled": 10}


def test_result_with_uuid_and_datetime_is_stored(db):
    """Les résultats contiennent souvent des UUID/dates : sérialisés, pas cause d'échec du job."""
    job = Job(type="demo")
    db.add(job)
    db.commit()
    run_job(db, job, lambda db, job: {"tender_id": uuid.uuid4(), "when": datetime.now(UTC)})
    db.refresh(job)
    assert job.status == JobStatus.done
    assert isinstance(job.result["tender_id"], str)


def test_commit_failure_marks_job_failed(db, monkeypatch):
    """Si le commit de succès échoue, le job ne doit pas rester `running` indéfiniment."""
    job = Job(type="demo")
    db.add(job)
    db.commit()
    real_commit = db.commit
    state = {"calls": 0}

    def flaky_commit():
        state["calls"] += 1
        if state["calls"] == 2:  # 1er commit = passage en running, 2e = commit de succès
            raise RuntimeError("connexion perdue")
        real_commit()

    monkeypatch.setattr(db, "commit", flaky_commit)
    run_job(db, job, lambda db, job: {"ok": True})
    db.refresh(job)
    assert job.status == JobStatus.failed
    assert "RuntimeError" in job.error


def test_dispatch_failure_marks_job_failed_and_raises(db, monkeypatch):
    def broken(job, kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(JobService, "dispatcher", staticmethod(broken))
    with pytest.raises(ServiceUnavailableError):
        JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=1)
    job = JobService.list(db, type="demo")[0]
    assert job.status == JobStatus.failed and "redis down" in job.error


def test_services_do_not_import_tasks():
    """Les tâches importent les services, jamais l'inverse (import circulaire dès la Phase 6)."""
    import importlib
    import sys

    sys.modules.pop("app.workers.tasks", None)
    sys.modules.pop("app.workers.tasks.demo", None)
    importlib.reload(importlib.import_module("app.services.jobs"))
    assert "app.workers.tasks.demo" not in sys.modules
    import app.workers.tasks  # noqa: F401 — on restaure l'enregistrement pour les tests suivants

    assert "demo" in REGISTRY
