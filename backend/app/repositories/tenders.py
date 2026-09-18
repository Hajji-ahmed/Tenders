"""Requêtes de liste des opportunités : filtres, tri (dont par score), pagination — liens, pièces
et score chargés en requêtes supplémentaires pour les compteurs et `score_total` ; kanban."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Tender, TenderScore, TenderSourceLink, TenderStatus, TenderStatusHistory

CLOSED_STATUSES = (TenderStatus.GAGNE, TenderStatus.PERDU, TenderStatus.ARCHIVE)
CLOSED_VISIBLE_DAYS = 90  # une fiche close reste sur le kanban 90 jours après son dernier changement


@dataclass
class TenderListParams:
    status: str | None = None
    sector: str | None = None
    country: str | None = None
    q: str | None = None
    deadline_before: date | None = None
    search_profile_id: UUID | None = None
    active_only: bool = True
    sort: str = "-created"
    page: int = 1
    size: int = 50


def _order(sort: str):
    match sort:
        case "created":
            return (Tender.created_at.asc(), Tender.title)
        case "deadline":
            return (Tender.deadline_at.asc().nulls_last(), Tender.created_at.desc())
        case "-deadline":
            return (Tender.deadline_at.desc().nulls_last(), Tender.created_at.desc())
        case "score":
            return (TenderScore.total.asc().nulls_last(), Tender.created_at.desc())
        case "-score":
            return (TenderScore.total.desc().nulls_last(), Tender.created_at.desc())
        case _:  # "-created"
            return (Tender.created_at.desc(), Tender.title)


def _with_relations(stmt):
    return stmt.options(
        selectinload(Tender.source_links), selectinload(Tender.documents), selectinload(Tender.score)
    )


def search(db: Session, p: TenderListParams) -> tuple[list[Tender], int]:
    stmt = select(Tender)
    if p.active_only:
        stmt = stmt.where(Tender.is_active.is_(True))
    if p.status:
        stmt = stmt.where(Tender.status == p.status)
    if p.sector:
        stmt = stmt.where(Tender.sector.ilike(p.sector))
    if p.country:
        stmt = stmt.where(Tender.country == p.country.upper())
    if p.search_profile_id:
        stmt = stmt.where(Tender.search_profile_id == p.search_profile_id)
    if p.q:
        pattern = f"%{p.q}%"
        stmt = stmt.where(or_(Tender.title.ilike(pattern), Tender.description.ilike(pattern)))
    if p.deadline_before:
        limit = datetime.combine(p.deadline_before, time(23, 59, 59), tzinfo=UTC)
        stmt = stmt.where(Tender.deadline_at <= limit)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if p.sort in ("score", "-score"):
        stmt = stmt.outerjoin(TenderScore, TenderScore.tender_id == Tender.id)
    rows = db.scalars(
        _with_relations(stmt).order_by(*_order(p.sort)).offset((p.page - 1) * p.size).limit(p.size)
    ).all()
    return list(rows), total


def get_detail(db: Session, tender_id: UUID) -> Tender | None:
    return db.scalar(
        select(Tender)
        .where(Tender.id == tender_id)
        .options(
            selectinload(Tender.source_links).selectinload(TenderSourceLink.source),
            selectinload(Tender.documents),
            selectinload(Tender.score),
        )
    )


def list_source_links(db: Session, tender_id: UUID) -> list[TenderSourceLink] | None:
    """Provenances d'une fiche dans l'ordre de collecte ; None si la fiche n'existe pas."""
    if db.scalar(select(Tender.id).where(Tender.id == tender_id)) is None:
        return None
    return list(
        db.scalars(
            select(TenderSourceLink)
            .where(TenderSourceLink.tender_id == tender_id)
            .options(selectinload(TenderSourceLink.source))
            .order_by(TenderSourceLink.collected_at, TenderSourceLink.url)
        )
    )


def list_status_history(db: Session, tender_id: UUID) -> list[TenderStatusHistory]:
    return list(
        db.scalars(
            select(TenderStatusHistory)
            .where(TenderStatusHistory.tender_id == tender_id)
            .order_by(TenderStatusHistory.changed_at, TenderStatusHistory.id)
        )
    )


def kanban(db: Session, *, now: datetime | None = None) -> dict[TenderStatus, list[Tender]]:
    """Fiches actives par statut, plus les fiches closes (gagné / perdu / archivé) des 90 derniers
    jours ; dans chaque colonne, meilleur score d'abord puis échéance la plus proche."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=CLOSED_VISIBLE_DAYS)
    stmt = (
        _with_relations(select(Tender))
        .outerjoin(TenderScore, TenderScore.tender_id == Tender.id)
        .where(
            or_(
                Tender.is_active.is_(True) & Tender.status.not_in(CLOSED_STATUSES),
                Tender.status.in_(CLOSED_STATUSES) & (Tender.updated_at >= since),
            )
        )
        .order_by(
            TenderScore.total.desc().nulls_last(),
            Tender.deadline_at.asc().nulls_last(),
            Tender.created_at.desc(),
        )
    )
    columns: dict[TenderStatus, list[Tender]] = {status: [] for status in TenderStatus}
    for tender in db.scalars(stmt):
        columns[TenderStatus(tender.status)].append(tender)
    return columns
