"""Sources de collecte : CRUD paginé + `POST /sources/{id}/test` qui joue une collecte limitée
(3 URL, 2 requêtes) sans rien enregistrer — pour vérifier une configuration avant de l'activer."""

from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core import deps
from app.core.db import get_db
from app.core.errors import NotFoundError
from app.models import SearchProfile, TenderSource
from app.schemas.tender import SourceTestOut, TenderSourceIn, TenderSourceOut, TenderSourceUpdate
from app.services.collect import CollectService
from app.services.query_builder import TENDER_TERM, build_queries

TEST_URL_LIMIT = 3
TEST_QUERY_LIMIT = 2

router = build_crud_router(
    TenderSource,
    TenderSourceIn,
    TenderSourceUpdate,
    TenderSourceOut,
    prefix="/sources",
    tag="sources",
    order_by=(TenderSource.priority, TenderSource.name),
    scoped_to_company=False,
    audit_action="source.updated",
)


@router.post("/{item_id}/test", response_model=SourceTestOut)
def test_source(
    item_id: UUID,
    search_profile_id: UUID | None = Query(
        None, description="Profil dont dériver les requêtes (défaut : premier actif)"
    ),
    db: Session = Depends(get_db),
):
    source = db.get(TenderSource, item_id)
    if source is None:
        raise NotFoundError("Source introuvable")
    profile = (
        db.get(SearchProfile, search_profile_id)
        if search_profile_id
        else db.scalar(
            select(SearchProfile).where(SearchProfile.is_active.is_(True)).order_by(SearchProfile.name)
        )
    )
    queries = build_queries(profile)[:TEST_QUERY_LIMIT] if profile else [TENDER_TERM]
    collect = CollectService(
        deps.get_web_search(),
        deps.get_crawler(),
        deps.get_tender_extractor(),
        rss=deps.get_rss(),
        js_crawler=deps.get_js_crawler(),
    )
    report = collect.collect_source(source, queries, limit=TEST_URL_LIMIT)
    return SourceTestOut(**report.as_dict(), queries=queries, candidates=report.candidates)
