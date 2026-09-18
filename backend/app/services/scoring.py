"""Moteur de scoring déterministe v1.0 (CdC §35, RB-004) : huit critères pondérés à 100, chacun
rendu avec son sous-score (0–100), sa raison en français et ce qui a été reconnu / manque. Aucun
appel réseau : la couche IA (services/score_service) ajoute la justification et un ajustement borné."""

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from app.models import Company, SearchProfile, Tender
from app.services.normalize import norm_text

SCORING_VERSION = "1.0"
WEIGHTS = {
    "sector": 20,
    "technologies": 15,
    "skills": 15,
    "country": 10,
    "budget": 10,
    "experience": 15,
    "certifications": 5,
    "eligibility": 10,
}
LABELS = {
    "sector": "Secteur",
    "technologies": "Technologies",
    "skills": "Compétences",
    "country": "Pays",
    "budget": "Budget",
    "experience": "Expérience",
    "certifications": "Certifications",
    "eligibility": "Éligibilité",
}
FUZZY_THRESHOLD = 85
STRENGTH_MIN, WEAKNESS_MAX = 75, 40


class SubScore(BaseModel):
    key: str
    score: float
    weight: int
    reason: str
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ScoreResult(BaseModel):
    total: float
    breakdown: list[SubScore]
    strengths: list[str]  # clés des critères ≥ 75
    weaknesses: list[str]  # clés des critères ≤ 40

    def summary(self) -> str:
        """Une ligne lisible des sous-scores, ex. « Secteur 100/100 · Technologies 60/100 · … »."""
        return " · ".join(f"{LABELS[s.key]} {s.score:g}/100" for s in self.breakdown)


def similar(a: str | None, b: str | None) -> bool:
    """Deux libellés équivalents à la casse, aux accents et à l'ordre des mots près."""
    na, nb = norm_text(a), norm_text(b)
    return bool(na and nb) and fuzz.token_set_ratio(na, nb) >= FUZZY_THRESHOLD


def _find(wanted: str, pool: list[str]) -> str | None:
    return next((p for p in pool if similar(wanted, p)), None)


def _tender_text(tender: Tender) -> str:
    return norm_text(f"{tender.title} {tender.description or ''}")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


# --- critères ----------------------------------------------------------------------------------


def score_sector(tender: Tender, company: Company, profile: SearchProfile | None) -> SubScore:
    key, weight = "sector", WEIGHTS["sector"]
    match = _find(tender.sector, company.sectors) if tender.sector else None
    if match:
        return SubScore(
            key=key,
            score=100,
            weight=weight,
            reason=f"Secteur « {tender.sector} » = secteur de l'entreprise « {match} »",
            matched=[match],
        )
    text = _tender_text(tender)
    keywords = [k for k in (profile.keywords if profile else []) if norm_text(k) and norm_text(k) in text]
    if keywords:
        return SubScore(
            key=key,
            score=50,
            weight=weight,
            reason=f"Secteur hors entreprise mais mot-clé du profil présent : {', '.join(keywords)}",
            matched=keywords,
        )
    label = f"« {tender.sector} »" if tender.sector else "inconnu"
    return SubScore(
        key=key,
        score=0,
        weight=weight,
        reason=f"Secteur {label} : aucun secteur de l'entreprise ni mot-clé du profil reconnu",
        missing=[tender.sector] if tender.sector else [],
    )


def score_technologies(tender: Tender, company: Company) -> SubScore:
    key, weight = "technologies", WEIGHTS["technologies"]
    required = [t for t in (tender.extra or {}).get("technologies", []) if t]
    if not required:
        return SubScore(
            key=key, score=60, weight=weight, reason="Technologies non précisées dans l'appel d'offres"
        )
    owned = [t.name for t in company.technologies]
    matched = [t for t in required if _find(t, owned)]
    missing = [t for t in required if t not in matched]
    score = round(100 * len(matched) / len(required), 1)
    reason = f"{len(matched)}/{len(required)} technologies demandées maîtrisées"
    return SubScore(key=key, score=score, weight=weight, reason=reason, matched=matched, missing=missing)


def score_skills(tender: Tender, company: Company) -> SubScore:
    key, weight = "skills", WEIGHTS["skills"]
    text = _tender_text(tender)
    matched = [s.name for s in company.skills if norm_text(s.name) and norm_text(s.name) in text]
    if not matched:
        return SubScore(
            key=key,
            score=0,
            weight=weight,
            reason="Aucune compétence de l'entreprise citée dans l'appel d'offres",
        )
    score = min(100, 25 * len(matched))
    return SubScore(
        key=key,
        score=score,
        weight=weight,
        reason=f"{_plural(len(matched), 'compétence citée', 'compétences citées')} dans l'appel d'offres",
        matched=matched,
    )


def score_country(tender: Tender, company: Company, profile: SearchProfile | None) -> SubScore:
    key, weight = "country", WEIGHTS["country"]
    if not tender.country:
        return SubScore(key=key, score=30, weight=weight, reason="Pays de l'appel d'offres inconnu")
    if company.country and tender.country == company.country:
        return SubScore(
            key=key,
            score=100,
            weight=weight,
            reason=f"Pays de l'entreprise ({tender.country})",
            matched=[tender.country],
        )
    if profile and tender.country in profile.countries:
        return SubScore(
            key=key,
            score=70,
            weight=weight,
            reason=f"Pays ciblé par le profil de recherche ({tender.country})",
            matched=[tender.country],
        )
    return SubScore(
        key=key,
        score=0,
        weight=weight,
        reason=f"Pays hors périmètre ({tender.country})",
        missing=[tender.country],
    )


def score_budget(tender: Tender, profile: SearchProfile | None) -> SubScore:
    key, weight = "budget", WEIGHTS["budget"]
    amount = tender.budget_max or tender.budget_min
    lo = profile.budget_min if profile else None
    hi = profile.budget_max if profile else None
    if amount is None or (lo is None and hi is None):
        return SubScore(
            key=key, score=50, weight=weight, reason="Budget non renseigné (appel d'offres ou profil)"
        )
    amount = float(amount)
    within = (lo is None or amount >= float(lo)) and (hi is None or amount <= float(hi))
    shown = f"{amount:,.0f} {tender.currency or ''}".replace(",", " ").strip()
    if within:
        return SubScore(
            key=key, score=100, weight=weight, reason=f"Budget {shown} dans la fourchette du profil"
        )
    return SubScore(
        key=key, score=20, weight=weight, reason=f"Budget {shown} hors de la fourchette du profil"
    )


def score_experience(tender: Tender, company: Company) -> SubScore:
    key, weight = "experience", WEIGHTS["experience"]
    text = _tender_text(tender)
    matched = [
        p.title
        for p in company.projects
        if p.sector and (similar(p.sector, tender.sector) or norm_text(p.sector) in text)
    ]
    score = {0: 0, 1: 50, 2: 75}.get(len(matched), 100)
    if not matched:
        return SubScore(key=key, score=0, weight=weight, reason="Aucun projet réalisé dans ce secteur")
    return SubScore(
        key=key,
        score=score,
        weight=weight,
        reason=f"{_plural(len(matched), 'projet réalisé', 'projets réalisés')} dans le secteur",
        matched=matched,
    )


def score_certifications(tender: Tender, company: Company) -> SubScore:
    key, weight = "certifications", WEIGHTS["certifications"]
    required = [c for c in (tender.extra or {}).get("required_certifications", []) if c]
    if not required:
        return SubScore(key=key, score=100, weight=weight, reason="Aucune certification exigée")
    valid = [c.name for c in company.certifications if c.is_valid]
    expired = [c.name for c in company.certifications if not c.is_valid]
    matched, missing = [], []
    for name in required:
        if _find(name, valid):
            matched.append(name)
        elif _find(name, expired):
            missing.append(f"{name} (expirée)")
        else:
            missing.append(name)
    score = round(100 * len(matched) / len(required), 1)
    reason = f"{len(matched)}/{len(required)} certifications exigées détenues et valides"
    return SubScore(key=key, score=score, weight=weight, reason=reason, matched=matched, missing=missing)


def score_eligibility(eligibility_ratio: float | None) -> SubScore:
    key, weight = "eligibility", WEIGHTS["eligibility"]
    if eligibility_ratio is None:
        return SubScore(
            key=key, score=50, weight=weight, reason="Éligibilité non évaluée (analyse des exigences à venir)"
        )
    ratio = min(1.0, max(0.0, eligibility_ratio))
    return SubScore(
        key=key,
        score=round(ratio * 100, 1),
        weight=weight,
        reason=f"{round(ratio * 100)} % des exigences éliminatoires satisfaites",
    )


# --- agrégation --------------------------------------------------------------------------------


def compute_score(
    tender: Tender, company: Company, profile: SearchProfile | None, eligibility_ratio: float | None
) -> ScoreResult:
    breakdown = [
        score_sector(tender, company, profile),
        score_technologies(tender, company),
        score_skills(tender, company),
        score_country(tender, company, profile),
        score_budget(tender, profile),
        score_experience(tender, company),
        score_certifications(tender, company),
        score_eligibility(eligibility_ratio),
    ]
    total = round(sum(s.score * s.weight for s in breakdown) / 100, 1)
    return ScoreResult(
        total=total,
        breakdown=breakdown,
        strengths=[s.key for s in breakdown if s.score >= STRENGTH_MIN],
        weaknesses=[s.key for s in breakdown if s.score <= WEAKNESS_MAX],
    )
