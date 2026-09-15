"""Respect de robots.txt (CdC §37) : un fichier par hôte, mis en cache ; injoignable = autorisé."""

import urllib.robotparser
from urllib.parse import urlparse

import httpx

ROBOTS_TIMEOUT = 10.0


class RobotsPolicy:
    def __init__(self, client: httpx.Client, user_agent: str):
        self._client = client
        self._user_agent = user_agent
        # Clé = "scheme://host[:port]" ; None = pas de règles (fichier absent, en erreur ou injoignable).
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            self._cache[origin] = self._load(origin)
        rules = self._cache[origin]
        return True if rules is None else rules.can_fetch(self._user_agent, url)

    def _load(self, origin: str) -> urllib.robotparser.RobotFileParser | None:
        try:
            response = self._client.get(f"{origin}/robots.txt", timeout=ROBOTS_TIMEOUT)
        except httpx.HTTPError:
            return None  # fail-open : on ne bloque pas la collecte sur un robots.txt injoignable
        if response.status_code != 200:
            return None
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser
