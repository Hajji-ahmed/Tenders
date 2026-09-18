"""Machine à états des opportunités et décision GO / NO-GO : transitions autorisées, historique,
audit, passage implicite par A_ANALYSER quand on décide depuis NOUVEAU ou NO_GO."""

import pytest
from sqlalchemy import select

from app.core.errors import ForbiddenTransition
from app.models import AuditLog, DecisionKind, Tender, TenderStatus
from app.services.tender_status import TRANSITIONS, decide, transition


def _tender(db, status: TenderStatus = TenderStatus.NOUVEAU) -> Tender:
    t = Tender(title="AO", status=status)
    db.add(t)
    db.flush()
    return t


def test_every_status_has_a_rule_and_archive_is_terminal():
    assert set(TRANSITIONS) == set(TenderStatus)
    assert TRANSITIONS[TenderStatus.ARCHIVE] == set()
    assert TRANSITIONS[TenderStatus.SOUMIS] == {TenderStatus.GAGNE, TenderStatus.PERDU}


def test_forbidden_transition_changes_nothing(db):
    t = _tender(db, TenderStatus.GO)
    with pytest.raises(ForbiddenTransition, match="GO → GAGNE"):
        transition(db, t, TenderStatus.GAGNE, comment=None, user=None)
    assert t.status == TenderStatus.GO and t.status_history == []
    with pytest.raises(ForbiddenTransition):
        transition(db, _tender(db, TenderStatus.ARCHIVE), TenderStatus.NOUVEAU, comment=None, user=None)


def test_transition_records_history_and_audit(db, user):
    t = _tender(db)
    transition(db, t, TenderStatus.A_ANALYSER, comment="À regarder", user=user)
    transition(db, t, TenderStatus.ARCHIVE, comment=None, user=None)

    assert t.status == TenderStatus.ARCHIVE
    assert [(h.from_status, h.to_status, h.comment, h.changed_by) for h in t.status_history] == [
        (TenderStatus.NOUVEAU, TenderStatus.A_ANALYSER, "À regarder", user.email),
        (TenderStatus.A_ANALYSER, TenderStatus.ARCHIVE, None, None),
    ]
    audits = list(db.scalars(select(AuditLog).where(AuditLog.action == "tender.status_changed")))
    assert len(audits) == 2 and audits[0].user_id == user.id
    assert audits[0].payload == {"from": "NOUVEAU", "to": "A_ANALYSER", "comment": "À regarder"}


def test_decide_go_from_a_analyser_records_decision_history_and_audit(db, user):
    t = _tender(db, TenderStatus.A_ANALYSER)
    decision = decide(db, t, DecisionKind.go, reason="Bon fit sectoriel", user=user)

    assert t.status == TenderStatus.GO
    assert decision.decision == DecisionKind.go and decision.decided_by == user.email
    assert t.decisions == [decision] and decision.reason == "Bon fit sectoriel"
    assert [(h.from_status, h.to_status) for h in t.status_history] == [
        (TenderStatus.A_ANALYSER, TenderStatus.GO)
    ]
    assert t.status_history[0].comment == "Bon fit sectoriel"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.decision"))
    assert audit is not None and audit.payload == {"decision": "go", "reason": "Bon fit sectoriel"}


def test_decide_from_nouveau_or_no_go_passes_through_a_analyser(db):
    fresh = _tender(db)
    decide(db, fresh, DecisionKind.go, reason=None, user=None)
    assert fresh.status == TenderStatus.GO
    assert [h.to_status for h in fresh.status_history] == [TenderStatus.A_ANALYSER, TenderStatus.GO]

    refused = _tender(db, TenderStatus.NO_GO)
    decide(db, refused, DecisionKind.go, reason="Nouvel élément", user=None)
    assert refused.status == TenderStatus.GO and len(refused.status_history) == 2

    direct = _tender(db)
    decide(db, direct, DecisionKind.no_go, reason="Hors périmètre", user=None)
    assert direct.status == TenderStatus.NO_GO and len(direct.status_history) == 1


def test_decide_is_refused_when_the_workflow_has_moved_on_or_is_already_decided(db):
    t = _tender(db, TenderStatus.SOUMIS)
    with pytest.raises(ForbiddenTransition):
        decide(db, t, DecisionKind.go, reason=None, user=None)
    assert t.decisions == [] and t.status == TenderStatus.SOUMIS

    refused = _tender(db, TenderStatus.NO_GO)
    with pytest.raises(ForbiddenTransition, match="déjà"):  # pas d'aller-retour A_ANALYSER → NO_GO
        decide(db, refused, DecisionKind.no_go, reason=None, user=None)
    assert refused.status_history == []
