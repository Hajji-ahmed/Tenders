"""CollectService : orchestration par source, sans base de données ni réseau (fakes uniquement)."""

import uuid

from app.ai.outputs import TenderCandidate
from app.connectors.crawl.fake import FakeCrawler
from app.connectors.extractor import FakeTenderExtractor
from app.connectors.rss import FakeRss
from app.connectors.search.fake import FakeWebSearch
from app.models import SourceKind, TenderSource
from app.services.collect import CollectService
from tests.factories import page, result


def _candidate(url: str, title: str = "AO") -> TenderCandidate:
    return TenderCandidate(is_tender=True, confidence=0.9, title=title, source_url=url)


def _source(kind: SourceKind, **kw) -> TenderSource:
    src = TenderSource(name=f"src-{kind}", kind=kind, **kw)
    src.id = uuid.uuid4()
    return src


def _service(search=None, crawler=None, extractor=None, rss=None) -> CollectService:
    return CollectService(
        search or FakeWebSearch(),
        crawler or FakeCrawler(),
        extractor or FakeTenderExtractor(),
        rss=rss or FakeRss(),
    )


def test_search_engine_source_queries_fetches_and_extracts():
    search = FakeWebSearch({"*": [result("https://ok/ao1", "AO 1"), result("https://ok/blog", "Blog")]})
    crawler = FakeCrawler(
        {
            "https://ok/ao1": page("https://ok/ao1", text="AO"),
            "https://ok/blog": page("https://ok/blog", text="x"),
        }
    )
    extractor = FakeTenderExtractor({"https://ok/ao1": _candidate("https://ok/ao1")})
    src = _source(SourceKind.search_engine, config={"include_domains": ["ok"], "max_results": 5})

    report = _service(search, crawler, extractor).collect_source(
        src, ["appel d'offres ERP", "appel d'offres SI"]
    )

    assert report.status == "ok" and report.error is None
    assert report.found == 2 and report.fetched == 2 and len(report.candidates) == 1
    assert report.candidates[0].source_url == "https://ok/ao1"
    assert report.titles["https://ok/ao1"] == "AO 1"
    assert [c["query"] for c in search.calls] == ["appel d'offres ERP", "appel d'offres SI"]
    assert search.calls[0]["include_domains"] == ["ok"] and search.calls[0]["max_results"] == 5


def test_known_urls_are_skipped_before_any_network_call():
    search = FakeWebSearch({"*": [result("https://ok/known"), result("https://ok/new")]})
    crawler = FakeCrawler({"https://ok/new": page("https://ok/new", text="AO")})
    extractor = FakeTenderExtractor({"https://ok/new": _candidate("https://ok/new")})

    report = _service(search, crawler, extractor).collect_source(
        _source(SourceKind.search_engine), ["q"], already_known=lambda url: url.endswith("/known")
    )

    assert crawler.calls == ["https://ok/new"]
    assert report.skipped_known == 1 and len(report.candidates) == 1


def test_rss_source_uses_feed_entries_and_reports_a_broken_feed():
    rss = FakeRss({"https://feed/rss": [result("https://feed/ao/2", "AO 2", source_name="rss")]})
    crawler = FakeCrawler({"https://feed/ao/2": page("https://feed/ao/2", text="AO 2")})
    extractor = FakeTenderExtractor({"https://feed/ao/2": _candidate("https://feed/ao/2")})
    service = _service(crawler=crawler, extractor=extractor, rss=rss)

    ok = service.collect_source(_source(SourceKind.rss, base_url="https://feed/rss"), ["ignoré"])
    assert ok.status == "ok" and len(ok.candidates) == 1

    broken = service.collect_source(_source(SourceKind.rss, base_url="https://broken/feed"), [])
    assert broken.status == "error" and "broken/feed" in (broken.error or "")
    assert broken.candidates == []


def test_portal_source_follows_listing_links_filtered_by_pattern():
    listing = page(
        "https://portail.ma/appels-offres",
        text="liste",
        links=[
            "https://portail.ma/ao/1",
            "https://portail.ma/ao/2",
            "https://portail.ma/actualites/3",
            "https://autre.org/ao/9",
        ],
    )
    crawler = FakeCrawler(
        {
            listing.url: listing,
            "https://portail.ma/ao/1": page("https://portail.ma/ao/1", text="AO 1"),
            "https://portail.ma/ao/2": page("https://portail.ma/ao/2", text="AO 2"),
        }
    )
    extractor = FakeTenderExtractor(
        {
            "https://portail.ma/ao/1": _candidate("https://portail.ma/ao/1"),
            "https://portail.ma/ao/2": _candidate("https://portail.ma/ao/2"),
        }
    )
    src = _source(
        SourceKind.portal,
        base_url="https://portail.ma",
        config={"listing_paths": ["/appels-offres"], "link_pattern": r"/ao/\d+", "max_links": 1},
    )

    report = _service(crawler=crawler, extractor=extractor).collect_source(src, [])

    assert report.found == 1 and len(report.candidates) == 1  # max_links=1 : seule la première
    assert (
        "https://portail.ma/actualites/3" not in crawler.calls
        and "https://autre.org/ao/9" not in crawler.calls
    )


def test_portal_listing_failure_is_reported_as_source_error():
    src = _source(SourceKind.website, base_url="https://down.ma", config={"listing_paths": ["/ao"]})
    report = _service().collect_source(src, [])
    assert report.status == "error" and "https://down.ma/ao" in (report.error or "")


def test_api_source_is_skipped():
    report = _service().collect_source(_source(SourceKind.api, base_url="https://api.x"), [])
    assert report.status == "skipped" and report.error


def test_unreadable_pages_and_extractor_errors_are_counted_not_fatal():
    search = FakeWebSearch(
        {"*": [result("https://ok/404"), result("https://ok/boom"), result("https://ok/ao")]}
    )
    crawler = FakeCrawler(
        {
            "https://ok/boom": page("https://ok/boom", text="?"),
            "https://ok/ao": page("https://ok/ao", text="AO"),
        }
    )

    class Extractor(FakeTenderExtractor):
        def extract(self, p):
            if p.url.endswith("/boom"):
                raise RuntimeError("LLM indisponible")
            return super().extract(p)

    extractor = Extractor({"https://ok/ao": _candidate("https://ok/ao")})
    report = _service(search, crawler, extractor).collect_source(_source(SourceKind.search_engine), ["q"])

    assert report.status == "ok" and len(report.candidates) == 1
    assert report.found == 3 and report.fetched == 2 and report.errors == 2
    assert "LLM indisponible" in (report.error or "")


def test_limit_caps_the_number_of_urls_processed():
    search = FakeWebSearch({"*": [result(f"https://ok/{i}") for i in range(10)]})
    crawler = FakeCrawler({f"https://ok/{i}": page(f"https://ok/{i}", text="x") for i in range(10)})
    report = _service(search, crawler).collect_source(_source(SourceKind.search_engine), ["q"], limit=3)
    assert report.found == 10 and report.fetched == 3 and len(crawler.calls) == 3
