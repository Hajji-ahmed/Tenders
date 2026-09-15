"""Recherche web via Tavily (https://tavily.com) — le moteur retenu par le cahier des charges."""

from typing import Any, Protocol

from app.connectors.search.base import SearchResult


class _TavilyClientLike(Protocol):
    def search(self, query: str, **kwargs: Any) -> dict: ...


class TavilySearch:
    source_name = "tavily"

    def __init__(self, api_key: str, *, client: _TavilyClientLike | None = None, search_depth: str = "basic"):
        if client is None:
            from tavily import TavilyClient  # import tardif : le SDK n'est chargé qu'en réel

            client = TavilyClient(api_key=api_key)
        self._client = client
        self.search_depth = search_depth  # "basic" (1 crédit) suffit : la page est recrawlée ensuite

    def search(
        self, query: str, *, max_results: int = 10, include_domains: list[str] | None = None
    ) -> list[SearchResult]:
        kwargs: dict[str, Any] = {"max_results": max_results, "search_depth": self.search_depth}
        if include_domains:
            kwargs["include_domains"] = include_domains
        data = self._client.search(query, **kwargs)
        results: list[SearchResult] = []
        for item in data.get("results", []):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    url=url,
                    title=(item.get("title") or url).strip(),
                    snippet=item.get("content") or "",
                    score=item.get("score"),
                    source_name=self.source_name,
                )
            )
        return results
