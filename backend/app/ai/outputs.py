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


class ScoreAssessment(BaseModel):
    """Lecture du modèle sur un score déterministe (RB-004 : justification obligatoire) : il explique,
    liste forces et faiblesses, et peut corriger le total de ± 10 points au plus, en le motivant."""

    justification: str = Field(
        description="3 à 5 phrases en français, factuelles, à partir des données fournies"
    )
    strengths: list[str] = Field(default_factory=list, description="Atouts, phrases courtes")
    weaknesses: list[str] = Field(default_factory=list, description="Faiblesses ou risques, phrases courtes")
    adjustment: int = Field(0, ge=-10, le=10, description="Correction du total, entre -10 et +10")
    adjustment_reason: str = Field("", description="Pourquoi cette correction (vide si 0)")
