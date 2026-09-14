"""Contrat de l'extracteur d'appel d'offres : une page crawlée → un `TenderCandidate` (ou `None`
si la page n'en décrit pas). Implémentation LLM en 3.4, fake scripté par URL pour les tests."""

from typing import Protocol

from app.ai.outputs import TenderCandidate
from app.connectors.crawl.base import CrawlResult


class TenderExtractor(Protocol):
    def extract(self, page: CrawlResult) -> TenderCandidate | None: ...


class FakeTenderExtractor:
    def __init__(self, mapping: dict[str, TenderCandidate] | None = None):
        self.mapping: dict[str, TenderCandidate] = dict(mapping or {})
        self.calls: list[str] = []

    def extract(self, page: CrawlResult) -> TenderCandidate | None:
        self.calls.append(page.url)
        return self.mapping.get(page.url)
