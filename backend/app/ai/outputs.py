"""Schémas de sortie structurée des modèles (contrats `LLMProvider.structured`)."""

import datetime as dt
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


class DatedItem(BaseModel):
    label: str = Field(description="Ex. « Date limite de remise des offres », « Visite de site »")
    # `dt.date` : le champ s'appelle `date`, le nom nu masquerait le type dans le corps de la classe.
    date: dt.date | None = Field(None, description="AAAA-MM-JJ, null si non écrite")
    source_page: int | None = Field(None, description="Numéro de page du corpus où l'information figure")


class CriterionOut(BaseModel):
    name: str
    weight: float | None = Field(None, description="Poids en %, ou points, tel qu'écrit ; null sinon")
    description: str | None = None
    source_page: int | None = None


class RequestedDocument(BaseModel):
    name: str
    mandatory: bool = Field(description="Pièce exigée sous peine de rejet (true) ou facultative (false)")
    source_page: int | None = None


class TenderAnalysisOutput(BaseModel):
    """Lecture structurée du dossier de consultation (CdC §35) : chaque élément daté, critère ou
    pièce demandée cite la page du corpus d'où il vient. Rien n'est inventé : absent ⇒ null / liste vide."""

    object: str = Field(description="Objet du marché en une ou deux phrases")
    organization: str | None = None
    reference: str | None = None
    budget: str | None = Field(None, description="Montant ou estimation tel qu'écrit, avec devise")
    duration: str | None = Field(None, description="Durée d'exécution ou du marché")
    location: str | None = Field(None, description="Lieu d'exécution")
    key_dates: list[DatedItem] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    evaluation_criteria: list[CriterionOut] = Field(default_factory=list)
    requested_documents: list[RequestedDocument] = Field(default_factory=list)
    eligibility_conditions: list[str] = Field(
        default_factory=list, description="Conditions d'admission / exclusion"
    )
    summary: str = Field(description="Résumé en 5 à 8 phrases, en français")


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
