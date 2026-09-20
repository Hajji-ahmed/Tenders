"""Schémas de la recherche et des opportunités : profils, sources, lancement, fiches `tenders`."""

import datetime as dt
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.ai.outputs import TenderCandidate
from app.models.scoring import DecisionKind
from app.models.tender import DownloadStatus, SourceKind, TenderStatus, Urgency
from app.schemas.company import _clean_tags

Name = Annotated[str, Field(min_length=1, max_length=255)]
CountryCode = Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Za-z]{3}$")]
Budget = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Days = Annotated[int, Field(ge=0, le=3650)]
Tags = list[str]


class _Out(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Profils de recherche -------------------------------------------------------------------------


class _SearchProfileFields(BaseModel):
    countries: list[CountryCode] | None = None
    regions: Tags | None = None
    sectors: Tags | None = None
    domains: Tags | None = None
    keywords: Tags | None = None
    budget_min: Budget | None = None
    budget_max: Budget | None = None
    currency: CurrencyCode | None = None
    organization_types: Tags | None = None
    market_types: Tags | None = None
    technologies: Tags | None = None
    skills: Tags | None = None
    certifications: Tags | None = None
    experience_level: str | None = Field(None, max_length=32)
    deadline_min_days: Days | None = None
    deadline_max_days: Days | None = None
    is_active: bool | None = None

    @field_validator(
        "regions", "sectors", "domains", "keywords", "organization_types", "market_types",
        "technologies", "skills", "certifications",
    )  # fmt: skip
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return _clean_tags(v)

    @field_validator("countries")
    @classmethod
    def _countries(cls, v: list[str] | None) -> list[str] | None:
        cleaned = _clean_tags([c.upper() for c in v]) if v is not None else None
        return cleaned

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class SearchProfileIn(_SearchProfileFields):
    name: Name

    @model_validator(mode="after")
    def _defaults(self) -> "SearchProfileIn":
        """Les listes absentes valent [] et le profil est actif par défaut (colonnes NOT NULL)."""
        for key in (
            "countries", "regions", "sectors", "domains", "keywords", "organization_types",
            "market_types", "technologies", "skills", "certifications",
        ):  # fmt: skip
            if getattr(self, key) is None:
                setattr(self, key, [])
        if self.is_active is None:
            self.is_active = True
        return self


class SearchProfileUpdate(_SearchProfileFields):
    name: Name | None = None


class SearchProfileOut(_Out):
    name: str
    countries: list[str]
    regions: list[str]
    sectors: list[str]
    domains: list[str]
    keywords: list[str]
    budget_min: Decimal | None
    budget_max: Decimal | None
    currency: str | None
    organization_types: list[str]
    market_types: list[str]
    technologies: list[str]
    skills: list[str]
    certifications: list[str]
    experience_level: str | None
    deadline_min_days: int | None
    deadline_max_days: int | None
    is_active: bool
    last_run_at: datetime | None


# --- Sources -------------------------------------------------------------------------------------


def _needs_url(kind: SourceKind) -> bool:
    return kind != SourceKind.search_engine


class TenderSourceIn(BaseModel):
    name: Name
    kind: SourceKind
    base_url: str | None = Field(None, max_length=1024)
    config: dict = Field(default_factory=dict)
    is_enabled: bool = True
    priority: int = Field(100, ge=0, le=1000)

    @model_validator(mode="after")
    def _url_required(self) -> "TenderSourceIn":
        if _needs_url(self.kind) and not (self.base_url or "").strip():
            raise ValueError(f"base_url est obligatoire pour une source de type {self.kind}")
        return self


class TenderSourceUpdate(BaseModel):
    name: Name | None = None
    kind: SourceKind | None = None
    base_url: str | None = Field(None, max_length=1024)
    config: dict | None = None
    is_enabled: bool | None = None
    priority: int | None = Field(None, ge=0, le=1000)


class TenderSourceOut(_Out):
    name: str
    kind: SourceKind
    base_url: str | None
    config: dict
    is_enabled: bool
    priority: int
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None


class SourceTestOut(BaseModel):
    """Résultat de POST /sources/{id}/test : le rapport de collecte (limité) et les candidats lus."""

    status: str
    error: str | None
    found: int
    skipped_known: int
    fetched: int
    errors: int
    extracted: int
    queries: list[str]
    candidates: list[TenderCandidate]


# --- Recherches ----------------------------------------------------------------------------------


class SearchIn(BaseModel):
    search_profile_id: UUID


# --- Opportunités --------------------------------------------------------------------------------

SortKey = Literal["created", "-created", "deadline", "-deadline", "score", "-score"]


class TenderSourceLinkOut(BaseModel):
    id: UUID
    source_id: UUID | None
    source_name: str | None = None
    url: str
    title_seen: str | None
    collected_at: datetime

    model_config = {"from_attributes": True}


class TenderDocumentOut(_Out):
    tender_id: UUID
    name: str
    source_url: str | None
    mime_type: str | None
    size_bytes: int | None
    download_status: DownloadStatus
    extraction_status: str
    page_count: int | None
    error: str | None


class TenderOut(_Out):
    reference: str | None
    title: str
    organization: str | None
    organization_type: str | None
    country: str | None
    region: str | None
    sector: str | None
    market_type: str | None
    budget_min: Decimal | None
    budget_max: Decimal | None
    currency: str | None
    published_at: date | None
    deadline_at: datetime | None
    questions_deadline_at: datetime | None
    source_url: str | None
    description: str | None
    summary: str | None
    status: TenderStatus
    urgency: Urgency
    is_active: bool
    search_profile_id: UUID | None
    days_left: int | None
    source_count: int
    document_count: int
    score_total: float | None = None  # propriété `Tender.score_total` (relation `score` chargée en liste)


class TenderDetailOut(TenderOut):
    extra: dict
    source_links: list[TenderSourceLinkOut]
    documents: list[TenderDocumentOut]


# --- Score, décision, statut ---------------------------------------------------------------------


class SubScoreOut(BaseModel):
    key: str
    score: float
    weight: int
    reason: str
    matched: list[str] = []
    missing: list[str] = []


class TenderScoreOut(BaseModel):
    id: UUID
    tender_id: UUID
    total: float
    breakdown: list[SubScoreOut]
    strengths: list[str]
    weaknesses: list[str]
    justification: str
    ai_adjustment: int
    model: str | None
    prompt_version: str | None
    scoring_version: str
    computed_at: datetime

    model_config = {"from_attributes": True}


class DecisionIn(BaseModel):
    decision: DecisionKind
    reason: str | None = Field(None, max_length=2000)


class StatusIn(BaseModel):
    status: TenderStatus
    comment: str | None = Field(None, max_length=2000)


class StatusHistoryOut(BaseModel):
    id: UUID
    from_status: TenderStatus | None
    to_status: TenderStatus
    comment: str | None
    changed_by: str | None
    changed_at: datetime

    model_config = {"from_attributes": True}


class KanbanColumnOut(BaseModel):
    status: TenderStatus
    items: list[TenderOut]


class KanbanOut(BaseModel):
    columns: list[KanbanColumnOut]


# --- Analyse du dossier --------------------------------------------------------------------------


class DatedItemOut(BaseModel):
    label: str
    # `dt.date` : l'annotation est évaluée après l'affectation, le nom nu résoudrait vers la valeur.
    date: dt.date | None = None
    source_page: int | None = None


class RequestedDocumentOut(BaseModel):
    name: str
    mandatory: bool
    source_page: int | None = None


class CriterionOut(BaseModel):
    id: UUID
    position: int
    name: str
    weight: float | None
    description: str | None
    source_page: int | None

    model_config = {"from_attributes": True}


class TenderAnalysisOut(BaseModel):
    id: UUID
    tender_id: UUID
    object: str
    organization: str | None
    reference: str | None
    budget: str | None
    duration: str | None
    location: str | None
    key_dates: list[DatedItemOut]
    deliverables: list[str]
    requested_documents: list[RequestedDocumentOut]
    eligibility_conditions: list[str]
    summary: str
    model: str | None
    prompt_version: str | None
    analyzed_at: datetime
    criteria: list[CriterionOut] = []

    model_config = {"from_attributes": True}
