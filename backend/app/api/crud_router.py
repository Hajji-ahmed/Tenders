"""Fabrique de routeurs CRUD paginés pour les sous-ressources simples (compétences, technologies…).

Routes produites sous `prefix` : GET "" (Page), POST "" (201), GET /{item_id}, PATCH /{item_id},
DELETE /{item_id} (204). Toutes exigent un utilisateur connecté et journalisent `profile.updated`
(entity_kind = nom de table). Avec `scoped_to_company=True` (défaut), les lignes sont rattachées à
l'entreprise unique (`company_id`) et un identifiant d'une autre entreprise renvoie 404.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, page_params
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError, ValidationError
from app.models import User
from app.schemas.common import Page
from app.services.company import CompanyService

AUDIT_ACTION = "profile.updated"


def apply_updates(obj: Any, data: dict[str, Any]) -> None:
    """Applique un PATCH partiel. Un `null` explicite sur une colonne NOT NULL est refusé (422, pas 500)."""
    columns = obj.__table__.columns
    for key, value in data.items():
        if value is None and key in columns and not columns[key].nullable:
            raise ValidationError(f"{key} ne peut pas être vide")
        setattr(obj, key, value)


def build_crud_router(
    model: type,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    *,
    prefix: str,
    tag: str,
    order_by: Any = None,
    scoped_to_company: bool = True,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag], dependencies=[Depends(get_current_user)])
    order = order_by if order_by is not None else model.created_at.desc()
    label = model.__name__
    page_model = Page[read_schema]  # type: ignore[valid-type]

    def _company_id(db: Session) -> UUID | None:
        return CompanyService.get_or_create(db).id if scoped_to_company else None

    def _get(db: Session, item_id: UUID) -> Any:
        obj = db.get(model, item_id)
        if obj is None or (scoped_to_company and obj.company_id != _company_id(db)):
            raise NotFoundError(f"{label} introuvable")
        return obj

    def _audit(db: Session, entity_id: UUID, user: User, **payload: Any) -> None:
        record_audit(
            db,
            action=AUDIT_ACTION,
            entity_kind=model.__tablename__,
            entity_id=entity_id,
            payload=payload,
            user_id=user.id,
        )

    @router.get("", response_model=page_model)
    def list_items(p: PageParams = Depends(page_params), db: Session = Depends(get_db)):
        query = select(model)
        if scoped_to_company:
            query = query.where(model.company_id == _company_id(db))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = db.scalars(query.order_by(order).offset(p.offset).limit(p.size)).all()
        return page_model(items=items, total=total, page=p.page, size=p.size)

    @router.post("", response_model=read_schema, status_code=201)
    def create_item(
        body: create_schema,  # type: ignore[valid-type]
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        data = body.model_dump()
        if scoped_to_company:
            data["company_id"] = _company_id(db)
        obj = model(**data)
        db.add(obj)
        db.flush()
        _audit(db, obj.id, user, op="create")
        return obj

    @router.get("/{item_id}", response_model=read_schema)
    def get_item(item_id: UUID, db: Session = Depends(get_db)):
        return _get(db, item_id)

    @router.patch("/{item_id}", response_model=read_schema)
    def update_item(
        item_id: UUID,
        body: update_schema,  # type: ignore[valid-type]
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        obj = _get(db, item_id)
        data = body.model_dump(exclude_unset=True)
        apply_updates(obj, data)
        db.flush()
        _audit(db, obj.id, user, op="update", fields=sorted(data))
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        obj = _get(db, item_id)
        db.delete(obj)
        db.flush()
        _audit(db, item_id, user, op="delete")
        return Response(status_code=204)

    return router
