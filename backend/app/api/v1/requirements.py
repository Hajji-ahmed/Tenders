"""Exigences d'un dossier : liste filtrée (`GET /tenders/{id}/requirements`) et mise à jour manuelle
(`PATCH /requirements/{id}` — statut, justification, obligatoire, priorité), auditée et marquée
`manual_status` pour survivre aux ré-extractions."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import RequirementCategory, RequirementStatus, Tender, TenderRequirement, User
from app.schemas.tender import RequirementOut, RequirementUpdate

router = APIRouter(tags=["requirements"], dependencies=[Depends(get_current_user)])


@router.get("/tenders/{tender_id}/requirements", response_model=list[RequirementOut])
def list_requirements(
    tender_id: UUID,
    status: RequirementStatus | None = None,
    category: RequirementCategory | None = None,
    mandatory: bool | None = Query(None, description="true : obligatoires seulement, false : facultatives"),
    db: Session = Depends(get_db),
):
    if db.get(Tender, tender_id) is None:
        raise NotFoundError("Opportunité introuvable")
    stmt = (
        select(TenderRequirement)
        .where(TenderRequirement.tender_id == tender_id)
        .options(selectinload(TenderRequirement.source_document))
        .order_by(TenderRequirement.code)
    )
    if status is not None:
        stmt = stmt.where(TenderRequirement.status == status)
    if category is not None:
        stmt = stmt.where(TenderRequirement.category == category)
    if mandatory is not None:
        stmt = stmt.where(TenderRequirement.is_mandatory.is_(mandatory))
    return list(db.scalars(stmt))


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def update_requirement(
    requirement_id: UUID,
    body: RequirementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.get(TenderRequirement, requirement_id)
    if req is None:
        raise NotFoundError("Exigence introuvable")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(req, key, value)
    if "status" in data or "justification" in data:
        req.manual_status = True  # une ré-extraction ne reviendra pas dessus
    db.flush()
    record_audit(
        db,
        action="requirement.updated",
        entity_kind="tender",
        entity_id=req.tender_id,
        payload={"code": req.code, "fields": sorted(data)},
        user_id=user.id,
    )
    db.flush()
    return req
