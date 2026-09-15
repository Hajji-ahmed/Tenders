"""Schémas de sortie structurée des modèles (contrats `LLMProvider.structured`)."""

from datetime import date

from pydantic import BaseModel, Field


class TenderCandidate(BaseModel):
    """Ce que l'extracteur lit dans une page web : un appel d'offres (ou non) et ses champs.
    Rien n'est inventé : un champ absent de la page reste `None`."""

    is_tender: bool = Field(description="La page décrit-elle un appel d'offres / consultation ?")
    confidence: float = Field(ge=0, le=1)
    title: str = ""
    organization: str | None = None
    organization_type: str | None = None
    reference: str | None = None
    country: str | None = None
    region: str | None = None
    sector: str | None = None
    market_type: str | None = None
    description: str = ""
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str | None = None
    published_at: date | None = None
    deadline_at: date | None = None
    questions_deadline_at: date | None = None
    source_url: str = ""
    document_urls: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    required_certifications: list[str] = Field(default_factory=list)
