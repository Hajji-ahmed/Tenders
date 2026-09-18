"""Modèles de la Phase 5 : score (un par opportunité, justifié — RB-004), décisions GO/NO-GO et
historique des statuts, tous supprimés avec l'opportunité."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import DecisionKind, Tender, TenderDecision, TenderScore, TenderStatus, TenderStatusHistory


def _score(tender: Tender, **over) -> TenderScore:
    base = dict(
        tender_id=tender.id,
        total=72.5,
        breakdown=[{"key": "sector", "score": 100, "weight": 20, "reason": "Secteur Énergie"}],
        strengths=["sector"],
        weaknesses=[],
        justification="Bonne adéquation sectorielle.",
        scoring_version="1.0",
    )
    base.update(over)
    return TenderScore(**base)


def test_score_unique_per_tender(db):
    t = Tender(title="AO 1")
    db.add(t)
    db.flush()
    db.add(_score(t))
    db.flush()
    db.add(_score(t, total=10))
    with pytest.raises(IntegrityError):
        db.flush()


def test_score_defaults_and_justification_required(db):
    t = Tender(title="AO 2")
    db.add(t)
    db.flush()
    score = _score(t)
    db.add(score)
    db.flush()
    assert score.ai_adjustment == 0 and score.model is None and score.prompt_version is None
    assert score.computed_at is not None and float(score.total) == 72.5
    assert t.score is score and t.score.breakdown[0]["key"] == "sector"

    other = Tender(title="AO sans justification")
    db.add(other)
    db.flush()
    db.add(TenderScore(tender_id=other.id, total=1, justification=None, scoring_version="1.0"))
    with pytest.raises(IntegrityError):  # RB-004 : un score sans justification n'existe pas
        db.flush()


def test_decisions_and_status_history_follow_the_tender(db):
    t = Tender(title="AO 3")
    db.add(t)
    db.flush()
    t.decisions.append(
        TenderDecision(decision=DecisionKind.go, reason="Bon fit", decided_by="test@innosustain.com")
    )
    t.status_history.append(
        TenderStatusHistory(from_status=TenderStatus.NOUVEAU, to_status=TenderStatus.A_ANALYSER)
    )
    t.status_history.append(
        TenderStatusHistory(
            from_status=TenderStatus.A_ANALYSER, to_status=TenderStatus.GO, comment="Décision GO"
        )
    )
    db.flush()
    db.expire(t)
    assert t.decisions[0].decided_at is not None and t.decisions[0].decision == DecisionKind.go
    assert [h.to_status for h in t.status_history] == [TenderStatus.A_ANALYSER, TenderStatus.GO]
    assert t.status_history[1].changed_at is not None and t.status_history[1].changed_by is None

    db.delete(t)
    db.flush()
    assert db.scalar(select(TenderDecision)) is None
    assert db.scalar(select(TenderStatusHistory)) is None
