from app.models.job import JobStatus
from app.services.jobs import JobService


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
    from app.models.job import Job
    from app.workers.tasks.demo import demo_task

    job = Job(type="demo")
    assert demo_task.run_inline(db, job, x=5) == {"doubled": 10}
