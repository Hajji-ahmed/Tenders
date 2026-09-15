from datetime import date

from app.ai.outputs import TenderCandidate
from app.services.normalize import country_code, embedding_text, normalize


def _cand(**kw) -> TenderCandidate:
    base = dict(is_tender=True, confidence=1.0, title="Refonte du SI")
    base.update(kw)
    return TenderCandidate(**base)


def test_normalize_country_and_reference():
    n = normalize(
        _cand(
            title="  Refonte   du SI ", organization="Ministère X", country="Maroc", reference="ao 12-2026/A"
        )
    )
    assert n.country == "MA" and n.norm_reference == "AO122026/A" and n.title == "Refonte du SI"
    assert n.norm_title == "refonte du si" and n.norm_org == "ministere x"


def test_fingerprint_stable_across_case_accents_and_spacing():
    a = normalize(_cand(title="Réfonte du  SI", organization="Ministère X", deadline_at=date(2026, 10, 1)))
    b = normalize(_cand(title="REFONTE DU SI !", organization="ministere x", deadline_at=date(2026, 10, 1)))
    assert a.fingerprint == b.fingerprint and len(a.fingerprint) == 40
    c = normalize(_cand(title="Refonte du SI", organization="Ministère X", deadline_at=date(2026, 10, 2)))
    assert c.fingerprint != a.fingerprint  # l'échéance fait partie de l'empreinte
    assert normalize(
        _cand(title="Refonte du SI", organization=None)
    ).fingerprint  # sans organisme ni échéance


def test_country_code_accepts_codes_french_and_english_names():
    assert country_code("ma") == "MA" and country_code(" MA ") == "MA"
    assert country_code("Maroc") == "MA" and country_code("Morocco") == "MA"
    assert country_code("Sénégal") == "SN" and country_code("Senegal") == "SN"
    assert country_code("Côte d'Ivoire") == "CI"
    assert country_code("Atlantide") is None and country_code(None) is None and country_code("") is None


def test_normalize_currency_reference_and_blank_fields():
    n = normalize(_cand(currency=" mad ", reference="", organization="  "))
    assert n.currency == "MAD" and n.norm_reference is None and n.organization is None and n.norm_org == ""
    assert normalize(_cand(currency="dirhams")).currency is None  # pas un code ISO 4217


def test_embedding_text_is_title_plus_truncated_description():
    n = normalize(_cand(title="AO", description="d" * 1000))
    text = embedding_text(n)
    assert text.startswith("AO") and len(text) <= 2 + 1 + 500
    assert embedding_text(normalize(_cand(title="AO", description=""))) == "AO"
