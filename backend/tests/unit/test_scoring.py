"""Moteur de scoring déterministe v1.0 : 8 sous-scores pondérés, chacun expliqué en français."""

from datetime import date, timedelta

from app.models import Certification, Company, Project, SearchProfile, Skill, Technology, Tender
from app.services.scoring import SCORING_VERSION, WEIGHTS, compute_score


def _company(**over) -> Company:
    today = date.today()
    c = Company(
        legal_name="Innovative & Sustainable Solutions",
        country="MA",
        sectors=["Environnement", "Énergie", "Conseil"],
        technologies=[Technology(name="Python"), Technology(name="PostgreSQL"), Technology(name="Power BI")],
        skills=[Skill(name="Audit énergétique"), Skill(name="Efficacité énergétique")],
        certifications=[
            Certification(name="ISO 14001", expires_at=today + timedelta(days=365)),
            Certification(name="ISO 9001", expires_at=today - timedelta(days=30)),
        ],
        projects=[
            Project(title="Audit énergétique de l'ONEE", sector="Énergie"),
            Project(title="Plan climat territorial", sector="Environnement"),
            Project(title="Éclairage LED de Salé", sector="Energie"),
            Project(title="Rénovation énergétique d'écoles", sector="énergie"),
        ],
    )
    for k, v in over.items():
        setattr(c, k, v)
    return c


def _tender(**over) -> Tender:
    base = dict(
        title="Audit énergétique de douze bâtiments communaux",
        description="Diagnostic des consommations, plan d'efficacité énergétique ; outils Python, Power BI.",
        sector="Énergie",
        country="MA",
        budget_max=500_000,
        extra={"technologies": ["Python", "Power BI"], "required_certifications": ["ISO 14001"]},
    )
    base.update(over)
    return Tender(**base)


def _profile(**over) -> SearchProfile:
    base = dict(
        name="Énergie Maroc",
        keywords=["audit énergétique"],
        countries=["MA", "SN"],
        budget_min=100_000,
        budget_max=2_000_000,
    )
    base.update(over)
    return SearchProfile(**base)


def _sub(result, key):
    return next(s for s in result.breakdown if s.key == key)


def test_weights_sum_to_100_and_breakdown_has_the_eight_keys():
    assert sum(WEIGHTS.values()) == 100 and SCORING_VERSION == "1.0"
    result = compute_score(_tender(), _company(), _profile(), None)
    assert [s.key for s in result.breakdown] == list(WEIGHTS)
    assert all(0 <= s.score <= 100 and s.reason for s in result.breakdown)
    assert all(s.weight == WEIGHTS[s.key] for s in result.breakdown)


def test_perfect_match_scores_above_90():
    result = compute_score(_tender(), _company(), _profile(), eligibility_ratio=1.0)
    assert result.total >= 90
    assert _sub(result, "sector").score == 100 and _sub(result, "country").score == 100
    assert _sub(result, "technologies").score == 100 and _sub(result, "technologies").matched == [
        "Python",
        "Power BI",
    ]
    assert _sub(result, "budget").score == 100 and _sub(result, "certifications").score == 100
    assert _sub(result, "experience").score == 100
    assert _sub(result, "experience").matched == [
        "Audit énergétique de l'ONEE",
        "Éclairage LED de Salé",
        "Rénovation énergétique d'écoles",
    ]  # « Plan climat territorial » (Environnement) n'est pas du secteur
    assert _sub(result, "eligibility").score == 100
    assert "sector" in result.strengths and result.weaknesses == []


def test_unknown_sector_gives_zero_with_a_reason_unless_a_keyword_matches():
    result = compute_score(
        _tender(sector=None, title="Fourniture de mobilier", description=""), _company(), _profile(), None
    )
    sector = _sub(result, "sector")
    assert sector.score == 0 and "secteur" in sector.reason.lower()
    assert "sector" in result.weaknesses

    keyword = compute_score(
        _tender(sector="Mobilier", title="Audit énergétique du siège"), _company(), _profile(), None
    )
    assert (
        _sub(keyword, "sector").score == 50 and "audit énergétique" in _sub(keyword, "sector").reason.lower()
    )


def test_expired_certification_is_listed_as_missing():
    tender = _tender(
        extra={"technologies": [], "required_certifications": ["ISO 9001", "ISO 27001", "ISO 14001"]}
    )
    result = compute_score(tender, _company(), _profile(), None)
    certs = _sub(result, "certifications")
    assert certs.matched == ["ISO 14001"]
    assert certs.missing == ["ISO 9001 (expirée)", "ISO 27001"]
    assert certs.score == round(100 / 3, 1)


def test_technologies_ratio_and_unspecified_case():
    partial = compute_score(
        _tender(extra={"technologies": ["Python", "Java", "Kafka", "Spark"]}), _company(), _profile(), None
    )
    tech = _sub(partial, "technologies")
    assert tech.score == 25 and tech.matched == ["Python"] and tech.missing == ["Java", "Kafka", "Spark"]

    unspecified = compute_score(_tender(extra={}), _company(), _profile(), None)
    assert (
        _sub(unspecified, "technologies").score == 60
        and "non précisé" in _sub(unspecified, "technologies").reason
    )


def test_country_budget_experience_and_eligibility_tiers():
    company = _company()
    profile = _profile()
    assert _sub(compute_score(_tender(country="SN"), company, profile, None), "country").score == 70
    assert _sub(compute_score(_tender(country=None), company, profile, None), "country").score == 30
    assert _sub(compute_score(_tender(country="FR"), company, profile, None), "country").score == 0

    assert _sub(compute_score(_tender(budget_max=None), company, profile, None), "budget").score == 50
    assert _sub(compute_score(_tender(budget_max=5_000_000), company, profile, None), "budget").score == 20
    assert _sub(compute_score(_tender(), company, None, None), "budget").score == 50  # sans profil : inconnu

    one_project = _company(projects=[Project(title="Audit énergétique", sector="Énergie")])
    assert _sub(compute_score(_tender(), one_project, profile, None), "experience").score == 50
    no_project = _company(projects=[])
    assert _sub(compute_score(_tender(), no_project, profile, None), "experience").score == 0

    eligibility = _sub(compute_score(_tender(), company, profile, None), "eligibility")
    assert eligibility.score == 50 and "non évaluée" in eligibility.reason
    assert _sub(compute_score(_tender(), company, profile, 0.8), "eligibility").score == 80


def test_skills_found_in_text_count_25_each():
    result = compute_score(_tender(), _company(), _profile(), None)
    skills = _sub(result, "skills")
    assert skills.score == 50 and sorted(skills.matched) == ["Audit énergétique", "Efficacité énergétique"]
    none = compute_score(
        _tender(title="Fourniture de véhicules", description=""), _company(), _profile(), None
    )
    assert _sub(none, "skills").score == 0


def test_total_is_weighted_and_rounded():
    result = compute_score(_tender(), _company(), _profile(), None)
    expected = round(sum(s.score * s.weight for s in result.breakdown) / 100, 1)
    assert result.total == expected
