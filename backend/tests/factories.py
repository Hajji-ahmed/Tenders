"""Constructeurs de données de test partagés (pages crawlées, résultats de recherche…)."""

from datetime import UTC, datetime

from app.connectors.crawl.base import CrawlResult
from app.connectors.search.base import SearchResult


def page(
    url: str,
    *,
    text: str = "",
    html: str | None = None,
    links: list[str] | None = None,
    status_code: int = 200,
) -> CrawlResult:
    return CrawlResult(
        url=url,
        status_code=status_code,
        html=html,
        text=text,
        links=links or [],
        fetched_at=datetime.now(tz=UTC),
    )


def result(url: str, title: str = "", *, source_name: str = "fake", snippet: str = "") -> SearchResult:
    return SearchResult(url=url, title=title or url, snippet=snippet, source_name=source_name)
