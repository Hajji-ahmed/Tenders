"""Modèles de documents de candidature : liste, création, lecture et modification du plan de
sections. Toucher au plan incrémente la version du modèle — les documents déjà rédigés gardent le
leur, mais on sait qu'il a changé."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, page_params
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import DocumentType, Template, User
from app.schemas.common import Page
from app.schemas.template import TemplateIn, TemplateOut, TemplateUpdate

router = APIRouter(prefix="/templates", tags=["templates"], dependencies=[Depends(get_current_user)])


def _get(db: Session, template_id: UUID) -> Template:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Modèle introuvable")
    return template


def _audit(db: Session, template: Template, user: User, action: str, **payload) -> None:
    record_audit(
        db,
        action=action,
        entity_kind="template",
        entity_id=template.id,
        payload={"name": template.name, "document_type": str(template.document_type), **payload},
        user_id=user.id,
    )
    db.flush()


@router.get("", response_model=Page[TemplateOut])
def list_templates(
    document_type: DocumentType | None = None,
    p: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    stmt = select(Template)
    if document_type is not None:
        stmt = stmt.where(Template.document_type == document_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Template.document_type, Template.name).offset(p.offset).limit(p.size)
    ).all()
    return Page[TemplateOut](
        items=[TemplateOut.model_validate(t) for t in rows], total=total, page=p.page, size=p.size
    )


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(body: TemplateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = Template(
        **body.model_dump(exclude={"sections"}),
        sections=[s.model_dump(mode="json") for s in body.sections],
        is_default=False,  # seul le semis pose des modèles par défaut
        version=1,
    )
    db.add(template)
    db.flush()
    _audit(db, template, user, "template.created")
    return template


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: UUID, db: Session = Depends(get_db)):
    return _get(db, template_id)


@router.patch("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template = _get(db, template_id)
    data = body.model_dump(exclude_unset=True, exclude={"sections"})
    for key, value in data.items():
        setattr(template, key, value)
    changed = set(data)
    if body.sections is not None:
        template.sections = [s.model_dump(mode="json") for s in body.sections]
        template.version += 1  # le plan a changé : ce n'est plus le même modèle
        changed.add("sections")
    db.flush()
    _audit(db, template, user, "template.updated", fields=sorted(changed))
    return template
