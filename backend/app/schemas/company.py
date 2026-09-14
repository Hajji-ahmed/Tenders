"""Schémas du profil entreprise et de ses sous-ressources.

Convention par entité X : `XIn` (création, champ principal requis), `XUpdate` (PATCH, tout optionnel —
un `null` explicite sur une colonne NOT NULL est refusé par le routeur CRUD), `XOut` (from_attributes).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.company import CertificationCategory, Company, SkillCategory, TechnologyCategory

Name = Annotated[str, Field(min_length=1, max_length=255)]
Level = Annotated[str, Field(max_length=32)]
CountryCode = Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Za-z]{3}$")]
Years = Annotated[int, Field(ge=0, le=80)]
Budget = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


def _clean_tags(values: list[str] | None) -> list[str] | None:
    """Supprime espaces et doublons des listes de libellés (secteurs, compétences, technologies)."""
    if values is None:
        return None
    seen: list[str] = []
    for value in values:
        item = value.strip()
        if item and item not in seen:
            seen.append(item)
    return seen


class _Out(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Profil ---------------------------------------------------------------------------------------


class CompanyProfileIn(BaseModel):
    """Corps du PUT /company/profile : partiel, seuls les champs envoyés sont modifiés."""

    legal_name: Name | None = None
    trade_name: str | None = Field(None, max_length=255)
    description: str | None = None
    country: CountryCode | None = None
    city: str | None = Field(None, max_length=128)
    address: str | None = None
    website: str | None = Field(None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=64)
    sectors: list[str] | None = None
    positioning: str | None = None

    @field_validator("legal_name")
    @classmethod
    def _legal_name_not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("la raison sociale ne peut pas être vide")
        return value

    @field_validator("country")
    @classmethod
    def _country_upper(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("sectors")
    @classmethod
    def _sectors_clean(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value)


class CompanyProfileOut(BaseModel):
    id: UUID
    legal_name: str
    trade_name: str | None
    description: str | None
    country: str | None
    city: str | None
    address: str | None
    website: str | None
    email: str | None
    phone: str | None
    sectors: list[str]
    positioning: str | None
    ai_summary: str | None
    ai_summary_updated_at: datetime | None
    counts: dict[str, int]
    updated_at: datetime

    @classmethod
    def from_company(cls, c: Company, counts: dict[str, int] | None = None) -> "CompanyProfileOut":
        profile = c.profile
        return cls(
            id=c.id,
            legal_name=c.legal_name,
            trade_name=c.trade_name,
            description=c.description,
            country=c.country,
            city=c.city,
            address=c.address,
            website=c.website,
            email=c.email,
            phone=c.phone,
            sectors=list(c.sectors or []),
            positioning=profile.positioning if profile else None,
            ai_summary=profile.ai_summary if profile else None,
            ai_summary_updated_at=profile.ai_summary_updated_at if profile else None,
            counts=counts or {},
            updated_at=c.updated_at,
        )


# --- Compétences ----------------------------------------------------------------------------------


class SkillIn(BaseModel):
    name: Name
    category: SkillCategory = SkillCategory.expertise
    level: Level | None = None
    description: str | None = None


class SkillUpdate(BaseModel):
    name: Name | None = None
    category: SkillCategory | None = None
    level: Level | None = None
    description: str | None = None


class SkillOut(_Out):
    name: str
    category: SkillCategory
    level: str | None
    description: str | None


# --- Technologies ---------------------------------------------------------------------------------


class TechnologyIn(BaseModel):
    name: Name
    category: TechnologyCategory = TechnologyCategory.other
    level: Level | None = None
    years_experience: Years | None = None


class TechnologyUpdate(BaseModel):
    name: Name | None = None
    category: TechnologyCategory | None = None
    level: Level | None = None
    years_experience: Years | None = None


class TechnologyOut(_Out):
    name: str
    category: TechnologyCategory
    level: str | None
    years_experience: int | None


# --- Certifications -------------------------------------------------------------------------------


class CertificationIn(BaseModel):
    name: Name
    issuer: str | None = Field(None, max_length=255)
    category: CertificationCategory = CertificationCategory.autre
    issued_at: date | None = None
    expires_at: date | None = None
    document_id: UUID | None = None


class CertificationUpdate(BaseModel):
    name: Name | None = None
    issuer: str | None = Field(None, max_length=255)
    category: CertificationCategory | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    document_id: UUID | None = None


class CertificationOut(_Out):
    name: str
    issuer: str | None
    category: CertificationCategory
    issued_at: date | None
    expires_at: date | None
    document_id: UUID | None
    is_valid: bool


# --- Experts --------------------------------------------------------------------------------------


class ExpertIn(BaseModel):
    full_name: Name
    role: str | None = Field(None, max_length=255)
    years_experience: Years | None = None
    skills: list[str] = []
    bio: str | None = None
    cv_document_id: UUID | None = None

    @field_validator("skills")
    @classmethod
    def _skills_clean(cls, value: list[str]) -> list[str]:
        return _clean_tags(value) or []


class ExpertUpdate(BaseModel):
    full_name: Name | None = None
    role: str | None = Field(None, max_length=255)
    years_experience: Years | None = None
    skills: list[str] | None = None
    bio: str | None = None
    cv_document_id: UUID | None = None

    @field_validator("skills")
    @classmethod
    def _skills_clean(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value)


class ExpertOut(_Out):
    full_name: str
    role: str | None
    years_experience: int | None
    skills: list[str]
    bio: str | None
    cv_document_id: UUID | None


# --- Projets --------------------------------------------------------------------------------------


class ProjectIn(BaseModel):
    title: Name
    client: str | None = Field(None, max_length=255)
    sector: str | None = Field(None, max_length=128)
    country: CountryCode | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: Budget | None = None
    currency: CurrencyCode | None = None
    technologies: list[str] = []
    description: str | None = None
    results: str | None = None
    is_reference: bool = False

    @field_validator("country", "currency")
    @classmethod
    def _codes_upper(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("technologies")
    @classmethod
    def _technologies_clean(cls, value: list[str]) -> list[str]:
        return _clean_tags(value) or []


class ProjectUpdate(BaseModel):
    title: Name | None = None
    client: str | None = Field(None, max_length=255)
    sector: str | None = Field(None, max_length=128)
    country: CountryCode | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: Budget | None = None
    currency: CurrencyCode | None = None
    technologies: list[str] | None = None
    description: str | None = None
    results: str | None = None
    is_reference: bool | None = None

    @field_validator("country", "currency")
    @classmethod
    def _codes_upper(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("technologies")
    @classmethod
    def _technologies_clean(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value)


class ProjectOut(_Out):
    title: str
    client: str | None
    sector: str | None
    country: str | None
    start_date: date | None
    end_date: date | None
    budget: float | None  # Numeric(14,2) en base, nombre JSON côté client
    currency: str | None
    technologies: list[str]
    description: str | None
    results: str | None
    is_reference: bool


# --- Références -----------------------------------------------------------------------------------


class ReferenceIn(BaseModel):
    client_name: Name
    project_id: UUID | None = None
    sector: str | None = Field(None, max_length=128)
    description: str | None = None
    contact_name: str | None = Field(None, max_length=255)
    contact_email: EmailStr | None = None
    document_id: UUID | None = None


class ReferenceUpdate(BaseModel):
    client_name: Name | None = None
    project_id: UUID | None = None
    sector: str | None = Field(None, max_length=128)
    description: str | None = None
    contact_name: str | None = Field(None, max_length=255)
    contact_email: EmailStr | None = None
    document_id: UUID | None = None


class ReferenceOut(_Out):
    client_name: str
    project_id: UUID | None
    sector: str | None
    description: str | None
    contact_name: str | None
    contact_email: str | None
    document_id: UUID | None
