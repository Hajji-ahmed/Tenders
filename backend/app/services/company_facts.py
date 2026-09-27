"""Faits vérifiables de l'entreprise (Phase 8) : la **seule** source de vérité passée aux modèles
(résumé du profil, scoring, éligibilité, génération). Ce qui n'est pas vérifiable n'y entre pas —
les certifications expirées et les documents inutilisables (RB-007) sont écartés, rien n'est déduit.
`as_text()` rend la forme lisible insérée dans les prompts."""

from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, CompanyDocument
from app.services.company import CompanyService


class NamedFact(BaseModel):
    name: str
    category: str | None = None
    level: str | None = None


class CertificationFact(BaseModel):
    name: str
    issuer: str | None = None
    expires_at: date | None = None


class ExpertFact(BaseModel):
    full_name: str
    role: str | None = None
    years_experience: int | None = None
    skills: list[str] = Field(default_factory=list)


class ProjectFact(BaseModel):
    title: str
    client: str | None = None
    sector: str | None = None
    country: str | None = None
    year: int | None = None
    technologies: list[str] = Field(default_factory=list)
    description: str | None = None
    is_reference: bool = False


class ReferenceFact(BaseModel):
    client_name: str
    sector: str | None = None
    description: str | None = None


class DocumentFact(BaseModel):
    name: str
    category: str
    expires_at: date | None = None


class CompanyFacts(BaseModel):
    """Ce que l'entreprise peut prouver, au jour de la lecture."""

    legal_name: str
    trade_name: str | None = None
    country: str | None = None
    city: str | None = None
    website: str | None = None
    positioning: str | None = None
    sectors: list[str] = Field(default_factory=list)
    skills: list[NamedFact] = Field(default_factory=list)
    technologies: list[NamedFact] = Field(default_factory=list)
    certifications: list[CertificationFact] = Field(default_factory=list)  # valides uniquement
    experts: list[ExpertFact] = Field(default_factory=list)
    projects: list[ProjectFact] = Field(default_factory=list)
    references: list[ReferenceFact] = Field(default_factory=list)
    documents: list[DocumentFact] = Field(default_factory=list)  # utilisables uniquement (RB-007)

    def as_text(self, *, include_documents: bool = True, include_empty: bool = True) -> str:
        """Forme lisible pour un prompt : une rubrique par nature de fait, « (aucun) » si vide.

        `include_documents=False` retire la base documentaire : les attestations et registres prouvent
        une éligibilité, ils ne décrivent pas l'entreprise (constaté en réel : le modèle présentait
        « plusieurs notes de capacités » comme une prestation).
        `include_empty=False` retire les rubriques vides : un modèle à qui l'on montre « (aucun) »
        commente l'absence (« l'entreprise ne mentionne aucune certification »), même quand le prompt
        le lui interdit — pour une présentation, mieux vaut qu'il ne voie jamais la rubrique."""
        identity = self.trade_name or self.legal_name or "(sans nom)"
        if self.trade_name and self.legal_name and self.trade_name != self.legal_name:
            identity += f" ({self.legal_name})"
        where = ", ".join(x for x in (self.city, self.country) if x)
        lines = [f"Entreprise : {identity}" + (f" — {where}" if where else "")]
        if self.website:
            lines.append(f"Site : {self.website}")
        if self.positioning:
            lines.append(f"Positionnement déclaré : {self.positioning}")
        rubrics: list[tuple[str, list[str]]] = [
            ("Secteurs", self.sectors),
            ("Compétences", [s.name for s in self.skills]),
            ("Technologies", [t.name for t in self.technologies]),
            (
                "Certifications valides",
                [
                    c.name + (f" (jusqu'au {c.expires_at:%d/%m/%Y})" if c.expires_at else "")
                    for c in self.certifications
                ],
            ),
            (
                "Experts",
                [
                    e.full_name
                    + (f" — {e.role}" if e.role else "")
                    + (f" — {e.years_experience} ans" if e.years_experience else "")
                    for e in self.experts
                ],
            ),
            (
                "Projets réalisés",
                [
                    p.title
                    + (f" — {p.client}" if p.client else "")
                    + (f" — secteur {p.sector}" if p.sector else "")
                    + (f" — {p.year}" if p.year else "")
                    for p in self.projects
                ],
            ),
            ("Références clients", [r.client_name for r in self.references]),
        ]
        if include_documents:
            rubrics.append(("Documents disponibles", [f"{d.name} ({d.category})" for d in self.documents]))
        lines += [_line(title, items) for title, items in rubrics if items or include_empty]
        return "\n".join(lines)


def _line(title: str, items: list[str]) -> str:
    return f"{title} : " + (", ".join(items) if items else "(aucun)")


def _year(day: date | None) -> int | None:
    return day.year if day is not None else None


def from_company(company: Company, documents: list[CompanyDocument]) -> CompanyFacts:
    """Construit les faits depuis les objets déjà chargés (aucune requête)."""
    return CompanyFacts(
        legal_name=company.legal_name,
        trade_name=company.trade_name,
        country=company.country,
        city=company.city,
        website=company.website,
        positioning=company.profile.positioning if company.profile else None,
        sectors=list(company.sectors or []),
        skills=sorted(
            (NamedFact(name=s.name, category=str(s.category), level=s.level) for s in company.skills),
            key=lambda x: x.name,
        ),
        technologies=sorted(
            (NamedFact(name=t.name, category=str(t.category), level=t.level) for t in company.technologies),
            key=lambda x: x.name,
        ),
        certifications=sorted(
            (
                CertificationFact(name=c.name, issuer=c.issuer, expires_at=c.expires_at)
                for c in company.certifications
                if c.is_valid  # RB-007 : une certification expirée n'est pas un fait opposable
            ),
            key=lambda x: x.name,
        ),
        experts=sorted(
            (
                ExpertFact(
                    full_name=e.full_name,
                    role=e.role,
                    years_experience=e.years_experience,
                    skills=list(e.skills or []),
                )
                for e in company.experts
            ),
            key=lambda x: x.full_name,
        ),
        projects=sorted(
            (
                ProjectFact(
                    title=p.title,
                    client=p.client,
                    sector=p.sector,
                    country=p.country,
                    year=_year(p.end_date or p.start_date),
                    technologies=list(p.technologies or []),
                    description=p.description,
                    is_reference=p.is_reference,
                )
                for p in company.projects
            ),
            key=lambda x: x.title,
        ),
        references=sorted(
            (
                ReferenceFact(client_name=r.client_name, sector=r.sector, description=r.description)
                for r in company.references
            ),
            key=lambda x: x.client_name,
        ),
        documents=sorted(
            (
                DocumentFact(name=d.name, category=str(d.category), expires_at=d.expires_at)
                for d in documents
                if d.is_usable  # RB-007 : brouillon, expiré ou archivé ⇒ pas un fait
            ),
            key=lambda x: x.name,
        ),
    )


def company_facts(db: Session) -> CompanyFacts:
    company = CompanyService.get_or_create(db)
    documents = list(db.scalars(select(CompanyDocument).where(CompanyDocument.company_id == company.id)))
    return from_company(company, documents)
