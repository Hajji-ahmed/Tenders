from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models.company import Certification, Expert, Project, Reference, Skill, Technology
from app.schemas.company import (
    CertificationIn,
    CertificationOut,
    CertificationUpdate,
    CompanyProfileIn,
    CompanyProfileOut,
    ExpertIn,
    ExpertOut,
    ExpertUpdate,
    ProjectIn,
    ProjectOut,
    ProjectUpdate,
    ReferenceIn,
    ReferenceOut,
    ReferenceUpdate,
    SkillIn,
    SkillOut,
    SkillUpdate,
    TechnologyIn,
    TechnologyOut,
    TechnologyUpdate,
)
from app.services.company import CompanyService

# Pas de `tags` sur le routeur parent : ils sont posés route par route (sinon doublon dans l'OpenAPI).
router = APIRouter(prefix="/company", dependencies=[Depends(get_current_user)])


@router.get("/profile", response_model=CompanyProfileOut, tags=["company"])
def get_profile(db: Session = Depends(get_db)):
    company = CompanyService.get_or_create(db)
    return CompanyProfileOut.from_company(company, CompanyService.counts(db, company))


@router.put("/profile", response_model=CompanyProfileOut, tags=["company"])
def put_profile(
    body: CompanyProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    company = CompanyService.update_profile(db, body.model_dump(exclude_unset=True), user_id=user.id)
    return CompanyProfileOut.from_company(company, CompanyService.counts(db, company))


# (modèle, schéma de création, schéma de mise à jour, schéma de lecture, segment d'URL, tri par défaut)
_SUB_RESOURCES = [
    (Skill, SkillIn, SkillUpdate, SkillOut, "skills", Skill.name.asc()),
    (Technology, TechnologyIn, TechnologyUpdate, TechnologyOut, "technologies", Technology.name.asc()),
    (
        Certification,
        CertificationIn,
        CertificationUpdate,
        CertificationOut,
        "certifications",
        Certification.name.asc(),
    ),
    (Expert, ExpertIn, ExpertUpdate, ExpertOut, "experts", Expert.full_name.asc()),
    (Project, ProjectIn, ProjectUpdate, ProjectOut, "projects", Project.created_at.desc()),
    (Reference, ReferenceIn, ReferenceUpdate, ReferenceOut, "references", Reference.client_name.asc()),
]

for _model, _create, _update, _read, _name, _order in _SUB_RESOURCES:
    router.include_router(
        build_crud_router(_model, _create, _update, _read, prefix=f"/{_name}", tag="company", order_by=_order)
    )
