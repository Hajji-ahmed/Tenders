import uuid

from app.services.jobs import JobService


def test_get_job(auth_client, db, run_jobs_inline):
    job = JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=3)
    r = auth_client.get(f"/api/v1/jobs/{job.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["result"] == {"doubled": 6}


def test_get_job_not_found(auth_client):
    r = auth_client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_list_jobs_filtered(auth_client, db, run_jobs_inline):
    JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=1)
    JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=-1)
    r = auth_client.get("/api/v1/jobs?type=demo&status=failed")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_jobs_require_auth(client):
    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 401
