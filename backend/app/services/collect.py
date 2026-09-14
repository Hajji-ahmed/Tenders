"""Collecte par source : découvrir des URL (moteur, flux RSS, page de listing), crawler chaque page,
en extraire un `TenderCandidate`. Aucune exception ne sort de `collect_source` : tout est rendu dans
un `SourceReport` (statut ok / error / skipped, compteurs, dernier message d'erreur). Pas de base de
données ici : l'idempotence passe par le prédicat `already_known(url)` fourni par l'appelant."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from app.ai.outputs import TenderCandidate
from app.connectors.crawl.base import CrawlerProvider
from app.connectors.extractor import TenderExtractor
from app.connectors.rss import FakeRss, RssConnector
from app.connectors.search.base import SearchResult, WebSearchProvider
from app.core import deps
from app.core.logging import get_logger
from app.models import SourceKind, TenderSource

log = get_logger("collect")

DEFAULT_MAX_RESULTS = 10  # par requête moteur
DEFAULT_MAX_LINKS = 30  # par page de listing
DEFAULT_MAX_URLS = 50  # pages crawlées par source et par recherche


@dataclass
class SourceReport:
    source_id: str | None
    kind: str
    status: str = "ok"  # ok | error | skipped
    error: str | None = None
    found: int = 0  # URL candidates découvertes (après dédoublonnage)
    skipped_known: int = 0  # déjà présentes en base : ni crawl ni extraction
    fetched: int = 0  # pages lues avec succès
    errors: int = 0  # pages illisibles ou extraction en échec
    candidates: list[TenderCandidate] = field(default_factory=list)
    titles: dict[str, str] = field(default_factory=dict)  # url → titre vu dans le moteur / le flux

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "error": self.error,
            "found": self.found,
            "skipped_known": self.skipped_known,
            "fetched": self.fetched,
            "errors": self.errors,
            "extracted": len(self.candidates),
        }


def _describe(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:1000]


class CollectService:
    def __init__(
        self,
        search: WebSearchProvider | None,
        crawler: CrawlerProvider,
        extractor: TenderExtractor,
        *,
        rss: RssConnector | FakeRss,
        js_crawler: CrawlerProvider | None = None,
        search_unavailable: str | None = None,
    ):
        """`search=None` (pas de clé Tavily) : seules les sources de type moteur sont en erreur, avec
        le message `search_unavailable` ; flux RSS et portails fonctionnent normalement."""
        self._search = search
        self._search_unavailable = search_unavailable or "Moteur de recherche non configuré"
        self._crawler = crawler
        self._js_crawler = js_crawler or crawler
        self._extractor = extractor
        self._rss = rss

    def collect_source(
        self,
        source: TenderSource,
        queries: list[str],
        *,
        already_known: Callable[[str], bool] = lambda url: False,
        limit: int | None = None,
    ) -> SourceReport:
        report = SourceReport(source_id=str(source.id) if source.id else None, kind=str(source.kind))
        if source.kind == SourceKind.api:
            report.status, report.error = "skipped", "Adaptateur API non implémenté pour cette source"
            return report
        try:
            results = self._discover(source, queries)
        except Exception as e:  # noqa: BLE001 — une source cassée est rapportée, jamais fatale
            log.warning("collect.discover_failed", source=str(source.id), error=_describe(e))
            report.status, report.error = "error", _describe(e)
            return report

        unique = list({r.url: r for r in results}.values())
        report.found = len(unique)
        config = source.config or {}
        crawler = self._js_crawler if config.get("render_js") else self._crawler
        cap = limit if limit is not None else int(config.get("max_urls", DEFAULT_MAX_URLS))
        processed = 0
        for r in unique:
            if processed >= cap:
                break
            if already_known(r.url):
                report.skipped_known += 1
                continue
            processed += 1
            report.titles[r.url] = r.title
            page = crawler.fetch(r.url, render_js=bool(config.get("render_js")))
            if not page.ok:
                report.errors += 1
                report.error = f"{r.url} : {page.error or f'HTTP {page.status_code}'}"
                continue
            report.fetched += 1
            try:
                candidate = self._extractor.extract(page)
            except Exception as e:  # noqa: BLE001 — l'extraction d'une page ne doit pas arrêter la source
                log.warning("collect.extract_failed", url=r.url, error=_describe(e))
                report.errors += 1
                report.error = f"{r.url} : {_describe(e)}"
                continue
            if candidate is None:
                continue
            if not candidate.title.strip():
                candidate.title = r.title  # titre du moteur / du flux en secours
            report.candidates.append(candidate)
        return report

    # --- découverte des URL par type de source -------------------------------------------------

    def _discover(self, source: TenderSource, queries: list[str]) -> list[SearchResult]:
        config = source.config or {}
        if source.kind == SourceKind.search_engine:
            if self._search is None:
                raise RuntimeError(self._search_unavailable)
            results: list[SearchResult] = []
            for query in queries:
                results.extend(
                    self._search.search(
                        query,
                        max_results=int(config.get("max_results", DEFAULT_MAX_RESULTS)),
                        include_domains=config.get("include_domains") or None,
                    )
                )
            return results
        if source.kind == SourceKind.rss:
            if not source.base_url:
                raise ValueError("Flux RSS sans URL")
            return self._rss.fetch(source.base_url)
        if source.kind in (SourceKind.portal, SourceKind.website):
            return self._discover_listing(source, config)
        raise ValueError(f"Type de source inconnu : {source.kind}")

    def _discover_listing(self, source: TenderSource, config: dict) -> list[SearchResult]:
        if not source.base_url:
            raise ValueError("Portail / site sans URL de base")
        pattern = re.compile(config["link_pattern"]) if config.get("link_pattern") else None
        max_links = int(config.get("max_links", DEFAULT_MAX_LINKS))
        base_host = (urlparse(source.base_url).hostname or "").lower()
        crawler = self._js_crawler if config.get("render_js") else self._crawler
        found: list[SearchResult] = []
        for path in config.get("listing_paths") or ["/"]:
            listing_url = urljoin(source.base_url, path)
            page = crawler.fetch(listing_url, render_js=bool(config.get("render_js")))
            if not page.ok:
                raise RuntimeError(
                    f"Page de listing illisible {listing_url} : {page.error or page.status_code}"
                )
            for link in page.links:
                host = (urlparse(link).hostname or "").lower()
                if host != base_host and not config.get("allow_external"):
                    continue  # on reste sur le domaine de la source, sauf demande explicite
                if pattern is not None and not pattern.search(link):
                    continue
                found.append(SearchResult(url=link, title=link, source_name=str(source.kind)))
                if len(found) >= max_links:
                    return found
        return found


def build_collect_service() -> CollectService:
    """Service de collecte branché sur les fournisseurs de `deps` ; le moteur de recherche est
    optionnel (sans clé, ses sources sont rapportées en erreur, le reste fonctionne)."""
    search: WebSearchProvider | None
    unavailable: str | None = None
    try:
        search = deps.get_web_search()
    except RuntimeError as e:
        search, unavailable = None, str(e)
    return CollectService(
        search,
        deps.get_crawler(),
        deps.get_tender_extractor(),
        rss=deps.get_rss(),
        js_crawler=deps.get_js_crawler(),
        search_unavailable=unavailable,
    )
