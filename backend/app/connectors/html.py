"""Nettoyage HTML partagé par les crawlers et le flux RSS : texte lisible et liens absolus."""

import re
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

# Balises sans contenu utile pour l'extraction (menus, scripts, pieds de page…).
NOISE_TAGS = (
    "head", "script", "style", "noscript", "template", "svg",
    "nav", "header", "footer", "aside", "form", "iframe",
)  # fmt: skip
# Balises qui délimitent un bloc de texte : un saut de ligne de chaque côté.
BLOCK_TAGS = (
    "p", "div", "br", "li", "ul", "ol", "table", "tr", "td", "th", "section", "article", "main",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "dl", "dt", "dd", "hr", "figure",
)  # fmt: skip
_SPACES = re.compile(r"[ \t\r\f\v ]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def html_to_text(html: str) -> str:
    """Texte d'une page sans son bruit : scripts/styles/navigation/pied de page retirés, un bloc par
    ligne, espaces normalisés, entités décodées. Vide si `html` est vide."""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    text = soup.get_text()
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n", "\n".join(line for line in lines if line)).strip()


def extract_links(html: str, base_url: str) -> list[str]:
    """Liens `<a href>` d'une page : absolus, sans fragment, dédupliqués (ordre conservé), ceux du
    même domaine que `base_url` en premier. Les schémas non web (mailto:, javascript:…) sont ignorés."""
    if not html:
        return []
    base_host = (urlparse(base_url).hostname or "").lower()
    soup = BeautifulSoup(html, "lxml")
    same: list[str] = []
    other: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith("#"):
            continue
        absolute, _ = urldefrag(urljoin(base_url, href))
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or absolute in seen:
            continue
        seen.add(absolute)
        (same if parsed.hostname.lower() == base_host else other).append(absolute)
    return same + other
