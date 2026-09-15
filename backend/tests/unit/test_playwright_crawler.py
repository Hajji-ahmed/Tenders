import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.connectors.crawl.httpx_crawler import HttpxCrawler
from app.connectors.crawl.playwright_crawler import PlaywrightCrawler, browser_available

PAGE = b"""<html><head><title>AO</title></head><body>
<h1>Appel d'offres</h1>
<script>document.body.insertAdjacentHTML('beforeend', '<p id="js">Objet rendu par JavaScript</p>');</script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (nom imposé par http.server)
        if self.path == "/robots.txt":
            body, ctype = b"User-agent: *\nDisallow: /prive\n", "text/plain"
        elif self.path.startswith("/prive"):
            body, ctype = b"secret", "text/html"
        else:
            body, ctype = PAGE, "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # silence
        pass


@pytest.fixture(scope="module")
def local_site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_playwright_respects_robots_without_launching_a_browser(local_site):
    page = PlaywrightCrawler().fetch(f"{local_site}/prive/ao")
    assert page.status_code == 451


def test_playwright_rejects_invalid_urls():
    assert PlaywrightCrawler().fetch("ftp://x").status_code == 0


@pytest.mark.skipif(not browser_available(), reason="Chromium Playwright non installé")
def test_playwright_renders_javascript_unlike_httpx(local_site):
    url = f"{local_site}/ao"
    static = HttpxCrawler(retry_wait=0).fetch(url)
    assert "rendu par JavaScript" not in static.text
    rendered = PlaywrightCrawler().fetch(url, timeout=30)
    assert rendered.status_code == 200
    assert "Appel d'offres" in rendered.text and "Objet rendu par JavaScript" in rendered.text
