from app.core.audit import record_audit
from app.models.audit import AuditLog


def test_record_audit(db, user):
    log = record_audit(
        db,
        action="tender.decision",
        entity_kind="tender",
        entity_id=None,
        payload={"decision": "go"},
        user_id=user.id,
    )
    db.flush()
    stored = db.get(AuditLog, log.id)
    assert stored.payload == {"decision": "go"}
    assert stored.user_id == user.id
    assert stored.created_at is not None


def test_request_id_header(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
    r2 = client.get("/api/v1/health")
    assert len(r2.headers["X-Request-ID"]) >= 8
