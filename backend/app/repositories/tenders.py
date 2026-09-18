"""Requêtes de liste des opportunités : filtres, tri, pagination (chargement des liens et pièces en
une requête supplémentaire pour les compteurs)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Tender, TenderSourceLink


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
        case _:  # "-created" et, jusqu'à la Phase 5, "score" / "-score"
            return (Tender.created_at.desc(), Tender.title)


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
    rows = db.scalars(
        stmt.options(selectinload(Tender.source_links), selectinload(Tender.documents))
        .order_by(*_order(p.sort))
        .offset((p.page - 1) * p.size)
        .limit(p.size)
    ).all()
    return list(rows), total


def get_detail(db: Session, tender_id: UUID) -> Tender | None:
    return db.scalar(
        select(Tender)
        .where(Tender.id == tender_id)
        .options(
            selectinload(Tender.source_links).selectinload(TenderSourceLink.source),
            selectinload(Tender.documents),
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
