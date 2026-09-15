from app.models import SearchProfile
from app.services.query_builder import build_queries


def test_build_queries_limits_and_dedupes():
    p = SearchProfile(name="p", keywords=["ERP", "data"], sectors=["santé"], countries=["MA", "FR"])
    q = build_queries(p, max_queries=4)
    assert len(q) == 4 and len(set(q)) == 4 and all("appel d'offres" in s for s in q)


def test_build_queries_uses_french_country_names_and_keeps_keyword_order():
    p = SearchProfile(name="p", keywords=["ERP"], countries=["MA", "SN", "XX"])
    assert build_queries(p) == [
        "appel d'offres ERP Maroc",
        "appel d'offres ERP Sénégal",
        "appel d'offres ERP XX",
    ]


def test_build_queries_ignores_blank_terms_and_duplicates():
    p = SearchProfile(name="p", keywords=[" ERP ", "erp", "", "SI"], sectors=[], countries=[])
    assert build_queries(p) == ["appel d'offres ERP", "appel d'offres SI"]


def test_build_queries_falls_back_to_a_generic_query():
    assert build_queries(SearchProfile(name="vide")) == ["appel d'offres"]
    assert build_queries(SearchProfile(name="pays", countries=["MA"])) == ["appel d'offres Maroc"]
