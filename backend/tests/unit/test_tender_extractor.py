import pytest

from app.ai.llm import FakeLLM
from app.ai.outputs import TenderCandidate
from app.ai.prompts import tender_extract
from app.connectors.llm_extractor import LLMTenderExtractor
from tests.factories import page


def test_extractor_returns_none_when_not_tender():
    llm = FakeLLM([TenderCandidate(is_tender=False, confidence=0.9)])
    assert LLMTenderExtractor(llm).extract(page("https://x/blog", text="Actualités")) is None


def test_extractor_fills_source_url_and_truncates():
    llm = FakeLLM([TenderCandidate(is_tender=True, confidence=0.8, title="AO SI")])
    cand = LLMTenderExtractor(llm).extract(page("https://x/ao", text="a" * 50_000))
    assert cand is not None and cand.source_url == "https://x/ao"
    assert len(llm.calls[0]["user"]) < 13_000
    assert llm.calls[0]["output"] is TenderCandidate and llm.calls[0]["tier"] == "fast"
    assert llm.calls[0]["system"] == tender_extract.SYSTEM


def test_extractor_rejects_low_confidence():
    llm = FakeLLM([TenderCandidate(is_tender=True, confidence=0.4, title="Peut-être")])
    assert LLMTenderExtractor(llm, min_confidence=0.6).extract(page("https://x/ao", text="…")) is None


def test_extractor_skips_unreadable_pages_without_calling_the_model():
    llm = FakeLLM([])
    extractor = LLMTenderExtractor(llm)
    assert extractor.extract(page("https://x/404", status_code=404)) is None
    assert extractor.extract(page("https://x/empty", text="   ")) is None
    assert llm.calls == []


def test_prompt_lists_page_links_and_candidate_document_urls_are_absolutized():
    llm = FakeLLM(
        [
            TenderCandidate(
                is_tender=True,
                confidence=0.9,
                title="AO",
                document_urls=["dce.pdf", "https://x/ao/reglement.pdf"],
            )
        ]
    )
    p = page(
        "https://x/ao/index.html", text="Appel d'offres", links=["https://x/ao/dce.pdf", "https://x/contact"]
    )
    cand = LLMTenderExtractor(llm).extract(p)
    assert cand is not None
    assert cand.document_urls == ["https://x/ao/dce.pdf", "https://x/ao/reglement.pdf"]
    assert (
        "https://x/ao/dce.pdf" in llm.calls[0]["user"] and "https://x/ao/index.html" in llm.calls[0]["user"]
    )


def test_prompt_is_versioned_and_states_the_rules():
    assert tender_extract.PROMPT_VERSION == "v1"
    for rule in ("is_tender", "null", "ISO"):
        assert rule in tender_extract.SYSTEM
    body = tender_extract.user_prompt(page("https://x/ao", text="Objet : SI"), max_chars=100)
    assert "https://x/ao" in body and "Objet : SI" in body


def test_extractor_propagates_model_errors():
    with pytest.raises(RuntimeError, match="FakeLLM"):
        LLMTenderExtractor(FakeLLM([])).extract(page("https://x/ao", text="Appel d'offres"))
