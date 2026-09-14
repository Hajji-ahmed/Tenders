import httpx

from app.connectors.rss import RssConnector


def test_rss_parses_items_and_skips_entries_without_link(fixtures_dir):
    items = RssConnector.parse((fixtures_dir / "feed.xml").read_text(encoding="utf-8"))
    assert [i.url for i in items] == [
        "https://portail.example.ma/ao/12-2026",
        "https://portail.example.ma/ao/13-2026",
    ]
    first = items[0]
    assert first.title == "AO 12/2026 — Refonte du système d'information"
    assert first.snippet == "Objet : refonte du SI de la commune.\nDate limite : 30/10/2026"  # HTML nettoyé
    assert first.source_name == "rss"


def test_rss_parse_tolerates_garbage():
    assert RssConnector.parse("<html>pas un flux</html>") == []
    assert RssConnector.parse("") == []


def test_rss_fetch_uses_http_and_reports_failures(fixtures_dir):
    xml = (fixtures_dir / "feed.xml").read_text(encoding="utf-8")

    def handler(request):
        if request.url.host == "feed.ok":
            return httpx.Response(200, text=xml, headers={"content-type": "application/rss+xml"})
        return httpx.Response(500)

    connector = RssConnector(transport=httpx.MockTransport(handler))
    assert len(connector.fetch("https://feed.ok/rss")) == 2
    try:
        connector.fetch("https://feed.broken/rss")
    except httpx.HTTPStatusError as e:
        assert e.response.status_code == 500
    else:
        raise AssertionError("un flux en erreur doit lever (la collecte capture l'erreur par source)")
