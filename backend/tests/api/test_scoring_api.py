"""Endpoints score / décision / statut / historique / kanban et tri par score de la liste."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.llm import FakeLLM
from app.ai.outputs import ScoreAssessment
from app.models import Tender, TenderScore, TenderStatus

URL = "/api/v1/tenders"


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(
        title="Audit énergétique de douze bâtiments communaux",
        organization="Commune de Rabat",
        sector="Énergie",
        country="MA",
        extra={"technologies": ["Python"], "required_certifications": ["ISO 14001"]},
    )
    db.add(t)
    db.flush()
    return t


def _score(db, t: Tender, total: float) -> TenderScore:
    s = TenderScore(tender_id=t.id, total=total, justification="j", scoring_version="1.0", breakdown=[])
    db.add(s)
    db.flush()
    return s


def test_post_score_enqueues_job_and_get_score_returns_breakdown(
    auth_client, db, run_jobs_inline, company, tender, monkeypatch
):
    from app.core import deps

    monkeypatch.setattr(
        deps,
        "_llm_override",
        FakeLLM(
            [
                ScoreAssessment(
                    justification="Adéquation correcte.", strengths=["Pays"], weaknesses=[], adjustment=3
                )
            ]
        ),
    )
    assert auth_client.get(f"{URL}/{tender.id}/score").status_code == 404  # pas encore calculé

    r = auth_client.post(f"{URL}/{tender.id}/score")
    assert r.status_code == 202, r.text
    assert r.json()["type"] == "calculate_match_score" and r.json()["entity_id"] == str(tender.id)

    body = auth_client.get(f"{URL}/{tender.id}/score").json()
    assert len(body["breakdown"]) == 8 and body["breakdown"][0]["key"] == "sector"
    assert body["justification"] == "Adéquation correcte." and body["ai_adjustment"] == 3
    assert body["total"] == 67.5 + 3 and body["scoring_version"] == "1.0" and body["computed_at"]
    assert body["strengths"] == ["Pays"]

    detail = auth_client.get(f"{URL}/{tender.id}").json()
    assert detail["score_total"] == 70.5 and detail["status"] == "A_ANALYSER"


def test_post_score_unknown_tender_is_404(auth_client):
    assert auth_client.post(f"{URL}/{uuid.uuid4()}/score").status_code == 404


def test_decision_and_status_endpoints_update_the_tender_and_history(auth_client, db, tender, user):
    r = auth_client.post(f"{URL}/{tender.id}/decision", json={"decision": "go", "reason": "Bon fit"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "GO" and r.json()["id"] == str(tender.id)

    r = auth_client.post(f"{URL}/{tender.id}/status", json={"status": "PREPARATION", "comment": "On y va"})
    assert r.status_code == 200 and r.json()["status"] == "PREPARATION"

    r = auth_client.post(f"{URL}/{tender.id}/status", json={"status": "GAGNE"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_transition"
    assert "PREPARATION → GAGNE" in r.json()["error"]["message"]

    history = auth_client.get(f"{URL}/{tender.id}/history").json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        ("NOUVEAU", "A_ANALYSER"),
        ("A_ANALYSER", "GO"),
        ("GO", "PREPARATION"),
    ]
    assert history[1]["comment"] == "Bon fit" and history[1]["changed_by"] == user.email
    assert history[2]["changed_at"]

    assert auth_client.post(f"{URL}/{tender.id}/decision", json={"decision": "peut-être"}).status_code == 422
    assert auth_client.post(f"{URL}/{uuid.uuid4()}/decision", json={"decision": "go"}).status_code == 404


def test_list_sorts_by_score_and_exposes_score_total(auth_client, db):
    rows = [Tender(title="Sans score"), Tender(title="Score 40"), Tender(title="Score 85")]
    for i, row in enumerate(rows):
        row.created_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=i)
    db.add_all(rows)
    db.flush()
    _score(db, rows[1], 40)
    _score(db, rows[2], 85)

    items = auth_client.get(URL, params={"sort": "-score"}).json()["items"]
    assert [t["title"] for t in items] == ["Score 85", "Score 40", "Sans score"]
    assert [t["score_total"] for t in items] == [85.0, 40.0, None]
    assert [t["title"] for t in auth_client.get(URL, params={"sort": "score"}).json()["items"]] == [
        "Score 40",
        "Score 85",
        "Sans score",
    ]


def test_kanban_groups_active_tenders_and_keeps_recent_closed_ones(auth_client, db):
    now = datetime.now(UTC)
    rows = [
        Tender(title="Nouveau", status=TenderStatus.NOUVEAU),
        Tender(title="Go", status=TenderStatus.GO),
        Tender(title="Expiré", status=TenderStatus.NOUVEAU, is_active=False),
        Tender(title="Gagné récent", status=TenderStatus.GAGNE, is_active=False),
        Tender(title="Archivé ancien", status=TenderStatus.ARCHIVE, is_active=False),
    ]
    db.add_all(rows)
    db.flush()
    rows[3].updated_at = now - timedelta(days=10)
    rows[4].updated_at = now - timedelta(days=120)
    db.flush()

    body = auth_client.get(f"{URL}/kanban").json()
    columns = {c["status"]: [t["title"] for t in c["items"]] for c in body["columns"]}
    assert list(columns) == [s.value for s in TenderStatus]  # toutes les colonnes, dans l'ordre du cycle
    assert columns["NOUVEAU"] == ["Nouveau"] and columns["GO"] == ["Go"]
    assert columns["GAGNE"] == ["Gagné récent"] and columns["ARCHIVE"] == []


def test_scoring_routes_require_auth(client, tender):
    assert client.get(f"{URL}/kanban").status_code == 401
    assert client.post(f"{URL}/{tender.id}/score").status_code == 401
