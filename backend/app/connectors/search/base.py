"""Contrat des moteurs de recherche web (Tavily en réel, `FakeWebSearch` en test)."""

from typing import Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str = ""
    score: float | None = None
    source_name: str  # tavily | rss | fake …


class WebSearchProvider(Protocol):
    def search(
        self, query: str, *, max_results: int = 10, include_domains: list[str] | None = None
    ) -> list[SearchResult]: ...
