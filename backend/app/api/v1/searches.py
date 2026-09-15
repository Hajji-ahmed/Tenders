"""Lancement d'une recherche : `POST /searches` enfile le job `search_tenders` (202 + JobOut) ;
`GET /searches` liste les dernières recherches (jobs de ce type)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError, ValidationError
from app.models import SearchProfile
from app.schemas.job import JobOut
from app.schemas.tender import SearchIn
from app.services.jobs import JobService

JOB_TYPE = "search_tenders"

router = APIRouter(prefix="/searches", tags=["searches"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=JobOut, status_code=202)
def launch_search(body: SearchIn, db: Session = Depends(get_db)):
    profile = db.get(SearchProfile, body.search_profile_id)
    if profile is None:
        raise NotFoundError("Profil de recherche introuvable")
    if not profile.is_active:
        raise ValidationError("Ce profil de recherche est désactivé", code="profile_inactive")
    return JobService.enqueue(
        db,
        JOB_TYPE,
        entity_kind="search_profile",
        entity_id=profile.id,
        search_profile_id=str(profile.id),
    )


@router.get("", response_model=list[JobOut])
def list_searches(limit: int = 20, db: Session = Depends(get_db)):
    return JobService.list(db, type=JOB_TYPE, limit=limit)
