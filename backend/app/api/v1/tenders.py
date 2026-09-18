"""Opportunités collectées : liste filtrée / triée / paginée et fiche détaillée (liens de provenance,
pièces). Les changements de statut et le scoring arrivent en Phase 5."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, page_params
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models.tender import TenderStatus
from app.repositories import tenders as tenders_repo
from app.schemas.common import Page
from app.schemas.tender import SortKey, TenderDetailOut, TenderOut, TenderSourceLinkOut

router = APIRouter(prefix="/tenders", tags=["tenders"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=Page[TenderOut])
def list_tenders(
    status: TenderStatus | None = None,
    sector: str | None = Query(None, max_length=128),
    country: str | None = Query(None, min_length=2, max_length=2),
    q: str | None = Query(None, max_length=200, description="Recherche dans le titre et la description"),
    deadline_before: date | None = None,
    search_profile_id: UUID | None = None,
    active_only: bool = True,
    sort: SortKey = "-created",
    p: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    params = tenders_repo.TenderListParams(
        status=status,
        sector=sector,
        country=country,
        q=q,
        deadline_before=deadline_before,
        search_profile_id=search_profile_id,
        active_only=active_only,
        sort=sort,
        page=p.page,
        size=p.size,
    )
    items, total = tenders_repo.search(db, params)
    return Page[TenderOut](
        items=[TenderOut.model_validate(t) for t in items], total=total, page=p.page, size=p.size
    )


@router.get("/{tender_id}", response_model=TenderDetailOut)
def get_tender(tender_id: UUID, db: Session = Depends(get_db)):
    tender = tenders_repo.get_detail(db, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    return tender


@router.get("/{tender_id}/sources", response_model=list[TenderSourceLinkOut])
def list_tender_sources(tender_id: UUID, db: Session = Depends(get_db)):
    """Annonces à l'origine de la fiche (une par URL), dans l'ordre de collecte : les doublons
    fusionnés (RB-001) y apparaissent comme autant de provenances."""
    links = tenders_repo.list_source_links(db, tender_id)
    if links is None:
        raise NotFoundError("Opportunité introuvable")
    return links
