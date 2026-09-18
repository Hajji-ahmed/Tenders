"""Cycle de vie d'une opportunité : transitions autorisées (machine à états du cahier des charges),
historisées et auditées ; décision GO / NO-GO motivée. Une décision prise depuis NOUVEAU ou NO_GO
passe implicitement par A_ANALYSER pour respecter la machine à états."""

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.errors import ForbiddenTransition
from app.models import DecisionKind, Tender, TenderDecision, TenderStatus, TenderStatusHistory, User

S = TenderStatus
TRANSITIONS: dict[TenderStatus, set[TenderStatus]] = {
    S.NOUVEAU: {S.A_ANALYSER, S.NO_GO, S.ARCHIVE},
    S.A_ANALYSER: {S.GO, S.NO_GO, S.ARCHIVE},
    S.GO: {S.PREPARATION, S.NO_GO},
    S.NO_GO: {S.A_ANALYSER, S.ARCHIVE},
    S.PREPARATION: {S.VALIDATION, S.NO_GO},
    S.VALIDATION: {S.PRET, S.PREPARATION},
    S.PRET: {S.SOUMIS, S.VALIDATION},
    S.SOUMIS: {S.GAGNE, S.PERDU},
    S.GAGNE: {S.ARCHIVE},
    S.PERDU: {S.ARCHIVE},
    S.ARCHIVE: set(),
}


def can_transition(current: TenderStatus, to: TenderStatus) -> bool:
    return to in TRANSITIONS[current]


def transition(
    db: Session, tender: Tender, to: TenderStatus, *, comment: str | None, user: User | None
) -> Tender:
    """Change le statut si la machine à états l'autorise ; historise (auteur lisible) et audite."""
    current = TenderStatus(tender.status)
    if not can_transition(current, to):
        raise ForbiddenTransition(f"Passage {current} → {to} impossible")
    tender.status_history.append(
        TenderStatusHistory(
            from_status=current, to_status=to, comment=comment, changed_by=user.email if user else None
        )
    )
    tender.status = to
    record_audit(
        db,
        action="tender.status_changed",
        entity_kind="tender",
        entity_id=tender.id,
        payload={"from": str(current), "to": str(to), "comment": comment},
        user_id=user.id if user else None,
    )
    db.flush()
    return tender


def decide(
    db: Session, tender: Tender, decision: DecisionKind, *, reason: str | None, user: User | None
) -> TenderDecision:
    """Enregistre la décision et amène la fiche en GO ou NO_GO (via A_ANALYSER si nécessaire)."""
    target = S.GO if decision == DecisionKind.go else S.NO_GO
    current = TenderStatus(tender.status)
    if current == target:
        raise ForbiddenTransition(f"Opportunité déjà en {target}")
    if (
        not can_transition(current, target)
        and can_transition(current, S.A_ANALYSER)
        and can_transition(S.A_ANALYSER, target)
    ):
        transition(db, tender, S.A_ANALYSER, comment="Réexamen avant décision", user=user)
    transition(db, tender, target, comment=reason, user=user)  # ForbiddenTransition si le dossier a avancé
    record = TenderDecision(decision=decision, reason=reason, decided_by=user.email if user else None)
    tender.decisions.append(record)
    record_audit(
        db,
        action="tender.decision",
        entity_kind="tender",
        entity_id=tender.id,
        payload={"decision": str(decision), "reason": reason},
        user_id=user.id if user else None,
    )
    db.flush()
    return record
