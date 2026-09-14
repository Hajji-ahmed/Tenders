"""Crawler de pages statiques (httpx) : robots.txt, 3 tentatives avec backoff sur erreurs réseau
et 5xx (jamais sur 4xx), corps plafonné, texte et liens extraits. Ne lève jamais : toute erreur
est rendue dans `CrawlResult(status_code=0, error=…)`."""

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from app.connectors.crawl.base import CrawlResult
from app.connectors.crawl.robots import RobotsPolicy
from app.connectors.html import extract_links, html_to_text

USER_AGENT = "tender-ai/1.0 (+https://innosustain.africa)"
ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
HTML_TYPES = ("text/html", "application/xhtml+xml")


@dataclass
class _Fetched:
    status_code: int
    content: bytes
    content_type: str
    encoding: str | None
    url: str


def is_web_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


class HttpxCrawler:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_bytes: int = 5_000_000,
        user_agent: str = USER_AGENT,
        respect_robots: bool = True,
        retries: int = 3,
        retry_wait: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.max_bytes = max_bytes
        self.respect_robots = respect_robots
        self.retries = retries
        self.retry_wait = retry_wait
        self._client = httpx.Client(
            transport=transport,
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": ACCEPT, "Accept-Language": "fr,en;q=0.8"},
        )
        self._robots = RobotsPolicy(self._client, user_agent)

    def fetch(self, url: str, *, render_js: bool = False, timeout: float = 30.0) -> CrawlResult:
        """`render_js` est ignoré ici (voir `PlaywrightCrawler`)."""
        if not is_web_url(url):
            return CrawlResult(url=url, status_code=0, error="URL invalide (http/https attendu)")
        if self.respect_robots and not self._robots.allowed(url):
            return CrawlResult(url=url, status_code=451, error="Interdit par robots.txt")
        try:
            fetched = self._get_with_retry(url, timeout)
        except httpx.HTTPError as e:
            return CrawlResult(url=url, status_code=0, error=f"{type(e).__name__}: {e}")
        return self._to_result(url, fetched)

    def _get_with_retry(self, url: str, timeout: float) -> _Fetched:
        retryer = Retrying(
            stop=stop_after_attempt(self.retries),
            wait=wait_exponential(multiplier=self.retry_wait, max=30),
            retry=retry_if_exception_type(httpx.TransportError)
            | retry_if_result(lambda f: f.status_code >= 500),
            reraise=True,  # dernière tentative en erreur réseau → l'exception remonte
        )
        try:
            return retryer(self._get, url, timeout)
        except RetryError as e:  # 5xx persistant : on rend la dernière réponse
            return e.last_attempt.result()

    def _get(self, url: str, timeout: float) -> _Fetched:
        with self._client.stream("GET", url, timeout=timeout) as response:
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= self.max_bytes:
                    break  # plafond : on n'avale pas un fichier de plusieurs centaines de Mo
            return _Fetched(
                status_code=response.status_code,
                content=b"".join(chunks)[: self.max_bytes],
                content_type=response.headers.get("content-type", ""),
                encoding=response.charset_encoding,
                url=str(response.url),
            )

    def _to_result(self, url: str, fetched: _Fetched) -> CrawlResult:
        if not 200 <= fetched.status_code < 300:
            return CrawlResult(url=url, status_code=fetched.status_code, error=f"HTTP {fetched.status_code}")
        ctype = fetched.content_type.split(";")[0].strip().lower()
        # Type absent ou text/plain (serveurs mal configurés) : on regarde si le corps ressemble à du HTML.
        sniffable = ctype in ("", "text/plain")
        looks_html = ctype in HTML_TYPES or (sniffable and fetched.content.lstrip()[:1] == b"<")
        if not looks_html:
            return CrawlResult(url=url, status_code=fetched.status_code)  # PDF, ZIP… : pas de texte ici
        html = fetched.content.decode(fetched.encoding or "utf-8", errors="replace")
        return CrawlResult(
            url=url,
            status_code=fetched.status_code,
            html=html,
            text=html_to_text(html),
            links=extract_links(html, fetched.url),
        )
