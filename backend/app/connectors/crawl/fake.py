"""Crawler simulé : pages scriptées par URL, 404 sinon. Aucun accès réseau."""

from app.connectors.crawl.base import CrawlResult


class FakeCrawler:
    def __init__(self, pages: dict[str, CrawlResult] | None = None):
        self.pages: dict[str, CrawlResult] = dict(pages or {})
        self.calls: list[str] = []

    def fetch(self, url: str, *, render_js: bool = False, timeout: float = 30.0) -> CrawlResult:
        self.calls.append(url)
        found = self.pages.get(url)
        if found is None:
            return CrawlResult(url=url, status_code=404, text="")
        return found
