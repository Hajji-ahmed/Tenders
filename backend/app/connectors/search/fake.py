"""Moteur de recherche simulé : résultats scriptés par sous-chaîne de requête."""

from urllib.parse import urlparse

from app.connectors.search.base import SearchResult


def _in_domains(url: str, domains: list[str]) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in domains)


class FakeWebSearch:
    """`results` : clé = sous-chaîne attendue dans la requête (première clé qui correspond, dans
    l'ordre d'insertion), `"*"` = résultats par défaut. Chaque appel est journalisé dans `calls`."""

    def __init__(self, results: dict[str, list[SearchResult]] | None = None):
        self.results: dict[str, list[SearchResult]] = dict(results or {})
        self.calls: list[dict] = []

    def search(
        self, query: str, *, max_results: int = 10, include_domains: list[str] | None = None
    ) -> list[SearchResult]:
        self.calls.append({"query": query, "max_results": max_results, "include_domains": include_domains})
        found = next((v for k, v in self.results.items() if k != "*" and k in query), None)
        if found is None:
            found = self.results.get("*", [])
        if include_domains:
            found = [r for r in found if _in_domains(r.url, include_domains)]
        return list(found[:max_results])
