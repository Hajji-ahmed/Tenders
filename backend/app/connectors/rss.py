"""Flux RSS / Atom des portails d'appels d'offres : chaque entrée devient un `SearchResult`
(source_name="rss") dont l'URL sera crawlée puis analysée comme une page ordinaire."""

import feedparser
import httpx

from app.connectors.crawl.httpx_crawler import USER_AGENT
from app.connectors.html import html_to_text
from app.connectors.search.base import SearchResult


class RssConnector:
    source_name = "rss"

    def __init__(self, *, timeout: float = 30.0, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            transport=transport, follow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}
        )

    @staticmethod
    def parse(xml: str) -> list[SearchResult]:
        """Entrées d'un flux (RSS 2.0, Atom…) ; celles sans lien sont ignorées, le résumé est
        débarrassé de son HTML. Un contenu qui n'est pas un flux donne une liste vide."""
        if not xml or not xml.strip():
            return []
        feed = feedparser.parse(xml)
        items: list[SearchResult] = []
        for entry in feed.entries:
            link = (entry.get("link") or "").strip()
            if not link.startswith(("http://", "https://")):
                continue
            summary = entry.get("summary") or entry.get("description") or ""
            items.append(
                SearchResult(
                    url=link,
                    title=(entry.get("title") or link).strip(),
                    snippet=html_to_text(summary),
                    source_name=RssConnector.source_name,
                )
            )
        return items

    def fetch(self, feed_url: str) -> list[SearchResult]:
        """Télécharge puis analyse un flux. Lève `httpx.HTTPError` si le flux est injoignable ou en
        erreur : la collecte (3.5) capture l'exception et la rapporte par source."""
        response = self._client.get(feed_url)
        response.raise_for_status()
        return self.parse(response.text)
