"""Crawler de pages dynamiques (Chromium headless via Playwright) : même règle robots.txt que le
crawler httpx, DOM lu après `networkidle`. Réservé aux sources `render_js: true` — un navigateur par
appel, donc bien plus lent et plus lourd que httpx. Sans Chromium installé (`playwright install
chromium`), `fetch` rend `status_code=0` avec l'erreur explicite ; rien ne plante."""

import os

import httpx

from app.connectors.crawl.base import CrawlResult
from app.connectors.crawl.httpx_crawler import USER_AGENT, is_web_url
from app.connectors.crawl.robots import RobotsPolicy
from app.connectors.html import extract_links, html_to_text


def browser_available() -> bool:
    """Chromium Playwright est-il installé sur cette machine ? (détection sans le lancer)"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            return bool(p.chromium.executable_path) and os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


class PlaywrightCrawler:
    def __init__(
        self, *, user_agent: str = USER_AGENT, respect_robots: bool = True, max_bytes: int = 5_000_000
    ):
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.max_bytes = max_bytes
        self._robots = RobotsPolicy(
            httpx.Client(follow_redirects=True, headers={"User-Agent": user_agent}), user_agent
        )

    def fetch(self, url: str, *, render_js: bool = True, timeout: float = 30.0) -> CrawlResult:
        if not is_web_url(url):
            return CrawlResult(url=url, status_code=0, error="URL invalide (http/https attendu)")
        if self.respect_robots and not self._robots.allowed(url):
            return CrawlResult(url=url, status_code=451, error="Interdit par robots.txt")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            return CrawlResult(url=url, status_code=0, error=f"Playwright non installé : {e}")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=self.user_agent)
                    response = page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                    status = response.status if response is not None else 0
                    html = page.content()[: self.max_bytes]
                    final_url = page.url
                finally:
                    browser.close()
        except Exception as e:  # navigateur absent, timeout, page inaccessible… : jamais d'exception
            return CrawlResult(url=url, status_code=0, error=f"{type(e).__name__}: {str(e)[:500]}")
        if not 200 <= status < 300:
            return CrawlResult(url=url, status_code=status, error=f"HTTP {status}")
        return CrawlResult(
            url=url,
            status_code=status,
            html=html,
            text=html_to_text(html),
            links=extract_links(html, final_url),
        )
