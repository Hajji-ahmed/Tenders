"""Contrat des crawlers (httpx pour les pages statiques, Playwright pour le JS, fake en test)."""

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, Field


class CrawlResult(BaseModel):
    url: str
    status_code: int
    html: str | None = None
    text: str = ""  # texte nettoyé (html_to_text), vide si la page n'a pas pu être lue
    links: list[str] = Field(default_factory=list)  # liens absolus trouvés dans la page
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class CrawlerProvider(Protocol):
    def fetch(self, url: str, *, render_js: bool = False, timeout: float = 30.0) -> CrawlResult: ...
