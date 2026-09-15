import httpx
import pytest

from app.connectors.crawl.httpx_crawler import HttpxCrawler


def _crawler(handler, **kw) -> HttpxCrawler:
    """Crawler branché sur un transport simulé, sans attente entre les tentatives."""
    return HttpxCrawler(transport=httpx.MockTransport(handler), retry_wait=0, **kw)


def _robots(allow: bool):
    return httpx.Response(
        200, text="User-agent: *\nDisallow: /prive\n" if allow else "User-agent: *\nDisallow: /\n"
    )


def test_retries_on_5xx_then_succeeds_and_extracts_text_and_links():
    calls = {"n": 0}

    def handler(request):
        if request.url.path == "/robots.txt":
            return _robots(allow=True)
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, text="<p>ok</p><a href='/dce.pdf'>DCE</a>")

    page = _crawler(handler).fetch("https://example.org/ao")
    assert page.status_code == 200 and page.text == "ok\nDCE"
    assert page.links == ["https://example.org/dce.pdf"]
    assert page.html is not None and calls["n"] == 2


def test_no_retry_on_4xx():
    calls = {"n": 0}

    def handler(request):
        if request.url.path == "/robots.txt":
            return _robots(allow=True)
        calls["n"] += 1
        return httpx.Response(404, text="nope")

    page = _crawler(handler).fetch("https://example.org/missing")
    assert page.status_code == 404 and page.text == "" and calls["n"] == 1


def test_robots_disallow_returns_451_without_fetching_the_page():
    fetched = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return _robots(allow=False)
        fetched.append(str(request.url))
        return httpx.Response(200, text="secret")

    page = _crawler(handler).fetch("https://example.org/ao")
    assert page.status_code == 451 and page.text == "" and fetched == []


def test_unreachable_robots_is_fail_open_and_cached_per_host():
    robots_calls = {"n": 0}

    def handler(request):
        if request.url.path == "/robots.txt":
            robots_calls["n"] += 1
            raise httpx.ConnectError("boom")
        return httpx.Response(200, text="<p>page</p>")

    crawler = _crawler(handler)
    assert crawler.fetch("https://example.org/a").text == "page"
    assert crawler.fetch("https://example.org/b").text == "page"
    assert robots_calls["n"] == 1


def test_network_error_after_retries_never_raises():
    attempts = {"n": 0}

    def handler(request):
        if request.url.path == "/robots.txt":
            return _robots(allow=True)
        attempts["n"] += 1
        raise httpx.ConnectError("down")

    page = _crawler(handler).fetch("https://example.org/ao")
    assert page.status_code == 0 and page.text == "" and attempts["n"] == 3
    assert page.error and "down" in page.error


def test_body_is_capped_at_max_bytes():
    def handler(request):
        if request.url.path == "/robots.txt":
            return _robots(allow=True)
        return httpx.Response(200, text="<p>" + "a" * 1000 + "</p>")

    page = _crawler(handler, max_bytes=100).fetch("https://example.org/big")
    assert page.status_code == 200 and len(page.html or "") <= 100


def test_non_html_content_is_not_parsed():
    def handler(request):
        if request.url.path == "/robots.txt":
            return _robots(allow=True)
        return httpx.Response(200, content=b"%PDF-1.4 ...", headers={"content-type": "application/pdf"})

    page = _crawler(handler).fetch("https://example.org/dce.pdf")
    assert page.status_code == 200 and page.text == "" and page.html is None


@pytest.mark.parametrize("bad", ["ftp://x/y", "not a url", ""])
def test_rejects_non_http_urls(bad):
    page = _crawler(lambda r: httpx.Response(200)).fetch(bad)
    assert page.status_code == 0 and page.error
