"""Garde anti-invention (Task 9.3) : relit ce que le modèle a écrit et signale ce qui ne se retrouve
pas dans les faits du profil — certification, ancienneté, client. Il n'empêche rien : il avertit,
et l'avertissement suit le document jusqu'à la relecture humaine (RB-005)."""

from datetime import date

import pytest

from app.services.company_facts import CompanyFacts, from_company
from app.services.fact_guard import FactGuard


@pytest.fixture
def facts(db, company) -> CompanyFacts:
    from app.models import Expert

    company.experts.append(Expert(full_name="Nadia F.", role="Chef de projet", years_experience=8))
    db.flush()
    return from_company(company, [])


def test_a_certification_absent_from_the_profile_is_flagged(facts):
    warnings = FactGuard().check("L'entreprise est certifiée ISO 27001 et ISO 14001.", facts)

    assert len(warnings) == 1 and "ISO 27001" in warnings[0]
    assert warnings[0].startswith("Élément non vérifié")


def test_expired_certifications_count_as_absent(db, company, facts):
    """ISO 9001 est au profil mais périmée : l'écrire dans une candidature est un risque."""
    assert any("ISO 9001" in w for w in FactGuard().check("Nous sommes certifiés ISO 9001.", facts))


def test_other_referentials_are_watched_too(facts):
    warnings = FactGuard().check("Nos équipes sont certifiées PMP et notre SOC 2 est à jour.", facts)
    assert len(warnings) == 2 and any("PMP" in w for w in warnings) and any("SOC 2" in w for w in warnings)


def test_experience_beyond_what_the_profile_shows_is_flagged(facts):
    ok = FactGuard().check("Nos experts cumulent 8 ans d'expérience sur ce type de marché.", facts)
    assert ok == []

    too_much = FactGuard().check("Une équipe forte de 20 ans d'expérience.", facts)
    assert len(too_much) == 1 and "20 ans" in too_much[0] and "8" in too_much[0]


def test_experience_is_not_flagged_when_the_profile_says_nothing(db, company):
    """Sans ancienneté renseignée, il n'y a rien à contredire : ne pas crier au loup."""
    facts = from_company(company, [])
    assert FactGuard().check("Vingt ans d'expérience, soit 20 ans de pratique.", facts) == []


def test_an_unknown_client_is_flagged_but_a_known_one_is_not(db, company, facts):
    known = FactGuard().check("Nous avons accompagné l'Office National X sur un audit.", facts)
    assert known == []

    unknown = FactGuard().check("Nous avons accompagné la Société Générale Marocaine.", facts)
    assert len(unknown) == 1 and "Société Générale Marocaine" in unknown[0]


def test_only_what_looks_like_an_organisation_is_suspected(facts):
    """Un titre de liste ou un intitulé de produit n'est pas un client : sans ce filtre, le relecteur
    reçoit des avertissements sur « Luminaires LED » et cesse de les lire (constaté en réel)."""
    text = (
        "### Moyens techniques\n"
        "- **Luminaires LED** : remplacement complet du parc.\n"
        "- **Télégestion Centralisée** : supervision à distance.\n"
        "Les pièces jointes : Attestation CNSS, Registre de Commerce."
    )
    assert FactGuard().check(text, facts) == []


def test_the_organisation_of_the_tender_is_never_a_false_alarm(facts):
    """Le document s'adresse à l'acheteur : le nommer n'est pas prétendre l'avoir eu pour client."""
    guard = FactGuard(allowed_names=["Commune de Salé"])
    assert guard.check("La Commune de Salé souhaite rénover son éclairage public.", facts) == []


def test_placeholders_and_plain_prose_raise_nothing(facts):
    text = (
        "## Notre approche\n\nL'entreprise intervient sur la transition énergétique au Maroc.\n"
        "Signataire : [À COMPLÉTER]. Lieu et date : [À COMPLÉTER].\n"
        "- Audit énergétique\n- Rénovation de l'éclairage public\n"
    )
    assert FactGuard().check(text, facts) == []


def test_each_element_is_reported_once(facts):
    warnings = FactGuard().check("ISO 27001 ici, ISO 27001 là, et encore ISO 27001.", facts)
    assert len(warnings) == 1


def test_valid_certifications_of_the_profile_pass(db, company):
    today = date.today()
    facts = from_company(company, [])
    assert any(c.name == "ISO 14001" and c.expires_at > today for c in facts.certifications)
    assert FactGuard().check("Nous sommes certifiés ISO 14001.", facts) == []
    assert FactGuard().check("Certification ISO14001 en cours de validité.", facts) == []


def test_warnings_are_readable_sentences(facts):
    warning = FactGuard().check("Certifiés ITIL depuis 2020.", facts)[0]
    assert (
        warning == "Élément non vérifié : « ITIL » ne figure pas dans les certifications valides du profil."
    )


def test_a_heading_followed_by_a_sentence_is_not_a_client(facts):
    """Constaté en réel : « ### Conclusion\\nNotre solution… » était lu comme « Conclusion Notre »."""
    text = "### Technologies\nLes luminaires sont télégérés.\n\n### Conclusion\nNotre équipe est prête."
    assert FactGuard().check(text, facts) == []


def test_no_warning_on_an_empty_text(facts):
    assert FactGuard().check("", facts) == []
    assert FactGuard().check("   ", facts) == []
