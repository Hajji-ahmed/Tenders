"""Modèles de documents de candidature (Phase 9) : chaque `Template` décrit un document à produire —
sa nature (lettre, offre technique, CV…) et le plan de ses sections. Une section porte ses
instructions de rédaction, sa longueur maximale et ce dont elle a besoin pour être écrite (faits de
l'entreprise, analyse du dossier, exigences, réponses, base documentaire) : la génération (9.3) ne
va chercher que cela, et rien d'autre ne parvient au modèle."""

import enum

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DocumentType(enum.StrEnum):
    """Les dix documents d'une candidature (CdC §36)."""

    presentation = "presentation"
    lettre_candidature = "lettre_candidature"
    offre_technique = "offre_technique"
    methodologie = "methodologie"
    comprehension_besoin = "comprehension_besoin"
    organisation_planning = "organisation_planning"
    equipe = "equipe"
    cv = "cv"
    references = "references"
    declaration = "declaration"


class SectionSource(enum.StrEnum):
    """Ce qu'une section a le droit de lire. Rien d'autre n'entre dans le contexte de génération."""

    company_facts = "company_facts"
    tender_analysis = "tender_analysis"
    requirements = "requirements"
    answers = "answers"
    kb = "kb"


class Template(UUIDMixin, TimestampMixin, Base):
    """Plan d'un document. `sections` : `[{key, title, instructions, max_words, requires}]` ; un
    modèle « répétable » (`repeat_for`) produit une section par expert ou par projet retenu."""

    __tablename__ = "templates"

    name: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[DocumentType] = mapped_column(String(32), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(8), default="fr")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # « experts » ou « projects » : le document se répète pour chaque élément retenu (CV, références).
    repeat_for: Mapped[str | None] = mapped_column(String(32))
