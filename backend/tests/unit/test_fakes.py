import pytest
from pydantic import BaseModel

from app.ai.llm import FakeLLM
from app.ai.outputs import TenderCandidate
from app.connectors.crawl.fake import FakeCrawler
from app.connectors.extractor import FakeTenderExtractor
from app.connectors.search.fake import FakeWebSearch
from app.core import deps
from tests.factories import page, result


class Answer(BaseModel):
    value: int


# --- FakeLLM ------------------------------------------------------------------------------------


def test_fake_llm_returns_scripted_structured_outputs_and_logs_calls():
    llm = FakeLLM([TenderCandidate(is_tender=True, confidence=0.9, title="X"), Answer(value=7)])
    cand = llm.structured(system="s", user="u", output=TenderCandidate)
    assert cand.title == "X"
    assert llm.structured(system="s2", user="u2", output=Answer, tier="strong").value == 7
    assert llm.calls[0] == {"system": "s", "user": "u", "output": TenderCandidate, "tier": "fast"}
    assert llm.calls[1]["tier"] == "strong"


def test_fake_llm_accepts_a_callable_and_serves_text():
    llm = FakeLLM(lambda user, output: output(value=len(user)), text_responses=["résumé"])
    assert llm.structured(system="", user="abcd", output=Answer).value == 4
    assert llm.text(system="", user="q") == "résumé"
    assert llm.calls[-1]["output"] is str


def test_fake_llm_fails_loudly_when_out_of_responses():
    llm = FakeLLM([])
    with pytest.raises(RuntimeError, match="FakeLLM"):
        llm.structured(system="", user="", output=Answer)


# --- FakeCrawler / FakeWebSearch / FakeTenderExtractor ----------------------------------------


def test_fake_crawler_serves_known_pages_and_404_otherwise():
    crawler = FakeCrawler({"https://x/ao": page("https://x/ao", text="Appel d'offres")})
    assert crawler.fetch("https://x/ao").text == "Appel d'offres"
    missing = crawler.fetch("https://x/none")
    assert missing.status_code == 404 and missing.text == "" and missing.url == "https://x/none"
    assert crawler.calls == ["https://x/ao", "https://x/none"]


def test_fake_search_matches_query_substring_then_default_and_filters_domains():
    search = FakeWebSearch(
        {
            "ERP": [result("https://a.ma/erp"), result("https://b.fr/erp")],
            "*": [result("https://a.ma/default")],
        }
    )
    assert [r.url for r in search.search("appel d'offres ERP Maroc")] == [
        "https://a.ma/erp",
        "https://b.fr/erp",
    ]
    assert [r.url for r in search.search("autre chose")] == ["https://a.ma/default"]
    assert [r.url for r in search.search("ERP", include_domains=["a.ma"])] == ["https://a.ma/erp"]
    assert len(search.search("ERP", max_results=1)) == 1
    assert search.calls[0]["query"] == "appel d'offres ERP Maroc"


def test_fake_extractor_maps_urls_to_candidates():
    cand = TenderCandidate(is_tender=True, confidence=0.8, title="AO", source_url="https://x/ao")
    extractor = FakeTenderExtractor({"https://x/ao": cand})
    assert extractor.extract(page("https://x/ao")) is cand
    assert extractor.extract(page("https://x/blog")) is None


# --- TenderCandidate ----------------------------------------------------------------------------


def test_tender_candidate_validates_confidence_and_defaults():
    c = TenderCandidate(is_tender=False, confidence=0)
    assert c.title == "" and c.document_urls == [] and c.deadline_at is None
    with pytest.raises(ValueError):
        TenderCandidate(is_tender=True, confidence=1.5)


# --- deps : fournisseurs injectables -------------------------------------------------------------


def test_deps_serve_empty_fakes_in_test_env_and_honor_overrides(
    fake_search, fake_crawler, fake_llm, fake_extractor
):
    assert deps.get_web_search() is fake_search
    assert deps.get_crawler() is fake_crawler
    assert deps.get_llm() is fake_llm
    assert deps.get_tender_extractor() is fake_extractor


def test_deps_default_to_fakes_without_fixtures():
    assert isinstance(deps.get_web_search(), FakeWebSearch)
    assert isinstance(deps.get_crawler(), FakeCrawler)
    assert isinstance(deps.get_llm(), FakeLLM)
    assert isinstance(deps.get_tender_extractor(), FakeTenderExtractor)
