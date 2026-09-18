from app.connectors.search.tavily import TavilySearch


class _Client:
    """Client Tavily simulé : renvoie une réponse au format de l'API et journalise les paramètres."""

    def __init__(self):
        self.calls: list[dict] = []

    def search(self, query, **kw):
        self.calls.append({"query": query, **kw})
        return {
            "results": [
                {"url": "https://portail.ma/ao/1", "title": "AO 1", "content": "Objet : SI", "score": 0.91},
                {"url": "https://x.org/no-title", "content": "…", "score": 0.4},
                {"title": "sans url"},
                # Constaté en réel : avec `include_domains` sur un domaine non indexé, Tavily renvoie
                # des pages sans rapport (public.com, fema.gov…) avec un score infime.
                {"url": "https://public.com", "title": "Stocks, Bonds, Crypto", "score": 0.04},
                {"url": "https://ancien.ma/ao", "title": "Sans score"},
            ]
        }


def test_tavily_maps_results_and_passes_search_options():
    client = _Client()
    search = TavilySearch(api_key="k", client=client)
    results = search.search("appel d'offres SI Maroc", max_results=5, include_domains=["portail.ma"])
    # le résultat à 0,04 est écarté (bruit) ; un résultat sans score est conservé
    assert [r.url for r in results] == [
        "https://portail.ma/ao/1",
        "https://x.org/no-title",
        "https://ancien.ma/ao",
    ]
    assert results[0].title == "AO 1" and results[0].snippet == "Objet : SI" and results[0].score == 0.91
    assert results[0].source_name == "tavily"
    assert results[1].title == "https://x.org/no-title"  # titre absent → l'URL sert de titre
    call = client.calls[0]
    assert call["query"] == "appel d'offres SI Maroc"
    assert call["max_results"] == 5 and call["include_domains"] == ["portail.ma"]
    assert call["search_depth"] == "basic"
