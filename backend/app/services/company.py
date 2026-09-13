from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.models.company import (
    Certification,
    Company,
    CompanyProfile,
    Expert,
    Project,
    Reference,
    Skill,
    Technology,
)
from app.models.document import CompanyDocument, DocumentStatus

# Sous-ressources comptées dans `CompanyProfileOut.counts` (les documents archivés ne comptent pas).
_COUNTED = {
    "skills": Skill,
    "technologies": Technology,
    "certifications": Certification,
    "experts": Expert,
    "projects": Project,
    "references": Reference,
    "documents": CompanyDocument,
}


class CompanyService:
    """Application mono-entreprise : une seule ligne `companies`, créée à la première lecture."""

    @staticmethod
    def get_or_create(db: Session) -> Company:
        company = db.scalar(select(Company).order_by(Company.created_at).limit(1))
        if company is None:
            company = Company(legal_name="", profile=CompanyProfile())
            db.add(company)
            db.flush()
        if company.profile is None:
            company.profile = CompanyProfile()
            db.flush()
        return company

    @staticmethod
    def counts(db: Session, company: Company) -> dict[str, int]:
        result: dict[str, int] = {}
        for name, model in _COUNTED.items():
            query = select(func.count()).select_from(model).where(model.company_id == company.id)
            if model is CompanyDocument:
                query = query.where(CompanyDocument.status != DocumentStatus.archived)
            result[name] = db.scalar(query) or 0
        return result

    @staticmethod
    def update_profile(db: Session, data: dict[str, Any], *, user_id: UUID | None) -> Company:
        """Mise à jour partielle : `data` ne contient que les champs envoyés (exclude_unset).
        `positioning` vit sur `CompanyProfile`, le reste sur `Company`."""
        company = CompanyService.get_or_create(db)
        fields = dict(data)
        if "positioning" in fields:
            company.profile.positioning = fields.pop("positioning")
        for key, value in fields.items():
            setattr(company, key, value)
        db.flush()
        record_audit(
            db,
            action="profile.updated",
            entity_kind="company",
            entity_id=company.id,
            payload={"fields": sorted(data)},
            user_id=user_id,
        )
        return company
