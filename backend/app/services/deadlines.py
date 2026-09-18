"""RB-002 : une opportunité dont l'échéance est passée sort de la liste (`is_active = False`) et
l'urgence d'une fiche active dépend des jours restants. Appliqué à l'ingestion (services/ingest) et
chaque nuit par la tâche beat `refresh_tender_deadlines` (workers/tasks/scheduled)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tender, Urgency


def compute_urgency(days_left: int | None) -> Urgency:
    """None → none ; > 14 j → low ; 8–14 → medium ; 3–7 → high ; ≤ 2 → critical."""
    if days_left is None:
        return Urgency.none
    if days_left > 14:
        return Urgency.low
    if days_left >= 8:
        return Urgency.medium
    if days_left >= 3:
        return Urgency.high
    return Urgency.critical


def refresh_tender_deadlines(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Désactive les fiches actives dont l'échéance est dépassée, puis recalcule l'urgence de toutes
    les fiches actives. Renvoie `{"expired": n, "updated": m}` (m = urgences modifiées). Ne commite pas."""
    now = now or datetime.now(UTC)
    expired = updated = 0
    for tender in db.scalars(select(Tender).where(Tender.is_active.is_(True))):
        if tender.deadline_at is not None and tender.deadline_at < now:
            tender.is_active, tender.urgency = False, Urgency.none
            expired += 1
            continue
        urgency = compute_urgency(tender.days_left)
        if tender.urgency != urgency:
            tender.urgency = urgency
            updated += 1
    db.flush()
    return {"expired": expired, "updated": updated}
