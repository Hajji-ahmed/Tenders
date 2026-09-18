"""Justification IA d'un score de pertinence (sortie : `ScoreAssessment`). Le modèle ne calcule pas
le score : il lit les sous-scores déterministes, la fiche de l'appel d'offres et le profil de
l'entreprise, puis explique, nuance (± 10 points au plus) et liste forces et faiblesses."""

from app.models import Company, Tender
from app.services.scoring import LABELS, ScoreResult

PROMPT_VERSION = "v1"

SYSTEM = """Tu es un chargé d'affaires qui aide un cabinet de conseil à décider s'il répond à un appel
d'offres. On te donne le profil de l'entreprise, la fiche de l'appel d'offres et un score de
pertinence calculé par des règles (sous-scores pondérés, avec ce qui a été reconnu et ce qui manque).

Règles :
- Réponds uniquement selon le schéma demandé, en français.
- justification : 3 à 5 phrases factuelles qui expliquent le score à partir des sous-scores et des
  données fournies. N'invente aucun fait sur l'entreprise ni sur l'appel d'offres.
- strengths / weaknesses : 2 à 4 phrases courtes chacune, concrètes (secteur, références, budget,
  certifications, pays, technologies, points d'attention).
- adjustment : entier entre -10 et +10. Corrige le total seulement si les règles ont manifestement
  sous-estimé ou surestimé la pertinence (ex. : une référence directement comparable non reconnue,
  une exigence bloquante visible dans la description). Sinon 0.
- adjustment_reason : la raison de la correction ; vide si adjustment = 0.
- Ne mentionne jamais que tu es une IA."""


def _lines(title: str, items: list[str]) -> str:
    return f"{title} : " + (", ".join(items) if items else "(aucun)")


def company_summary(company: Company) -> str:
    valid = [c.name for c in company.certifications if c.is_valid]
    expired = [c.name for c in company.certifications if not c.is_valid]
    projects = [f"{p.title}" + (f" ({p.sector})" if p.sector else "") for p in company.projects]
    parts = [
        f"Entreprise : {company.trade_name or company.legal_name or '(sans nom)'}"
        + (f", {company.country}" if company.country else ""),
    ]
    if company.profile and (company.profile.ai_summary or company.profile.positioning):
        parts.append(f"Positionnement : {company.profile.ai_summary or company.profile.positioning}")
    parts += [
        _lines("Secteurs", company.sectors),
        _lines("Compétences", [s.name for s in company.skills]),
        _lines("Technologies", [t.name for t in company.technologies]),
        _lines("Certifications valides", valid),
        _lines("Certifications expirées", expired),
        _lines("Projets réalisés", projects),
    ]
    return "\n".join(parts)


def tender_summary(tender: Tender, max_description: int = 2_000) -> str:
    extra = tender.extra or {}
    budget = (
        f"{tender.budget_min or ''}–{tender.budget_max or ''} {tender.currency or ''}".strip(" –")
        if (tender.budget_min or tender.budget_max)
        else "(non renseigné)"
    )
    deadline = tender.deadline_at.date().isoformat() if tender.deadline_at else "(inconnue)"
    unknown = "(inconnu)"
    return "\n".join(
        [
            f"Titre : {tender.title}",
            f"Organisme : {tender.organization or unknown} — Pays : {tender.country or unknown}",
            f"Secteur : {tender.sector or unknown} — Type de marché : {tender.market_type or unknown}",
            f"Budget : {budget} — Échéance : {deadline}",
            _lines("Technologies demandées", list(extra.get("technologies", []))),
            _lines("Certifications exigées", list(extra.get("required_certifications", []))),
            f"Description : {(tender.description or '(aucune)')[:max_description]}",
        ]
    )


def breakdown_summary(result: ScoreResult) -> str:
    lines = [f"Total calculé : {result.total}/100"]
    for s in result.breakdown:
        line = f"- {LABELS[s.key]} ({s.weight} %) : {s.score:g}/100 — {s.reason}"
        if s.matched:
            line += f" | reconnu : {', '.join(s.matched)}"
        if s.missing:
            line += f" | manque : {', '.join(s.missing)}"
        lines.append(line)
    return "\n".join(lines)


def user_prompt(tender: Tender, company: Company, result: ScoreResult) -> str:
    return "\n\n".join(
        [
            "PROFIL DE L'ENTREPRISE\n" + company_summary(company),
            "APPEL D'OFFRES\n" + tender_summary(tender),
            "SCORE CALCULÉ PAR LES RÈGLES\n" + breakdown_summary(result),
        ]
    )
