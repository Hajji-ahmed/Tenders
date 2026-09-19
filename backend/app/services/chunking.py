"""Découpage du texte extrait en morceaux indexables : d'abord aux paragraphes, puis aux phrases,
jamais au milieu d'un mot ; recouvrement entre morceaux consécutifs d'une même page ; page
d'origine et titre de section (« Article 3 — … », « 3.2 … ») conservés pour citer les sources."""

import re

from pydantic import BaseModel

from app.services.extraction import ExtractedPage

DEFAULT_MAX_CHARS = 1_500
DEFAULT_OVERLAP = 200

_PARAGRAPHS = re.compile(r"\n+")
_SENTENCES = re.compile(r"(?<=[.!?;:])\s+")
_HEADING = re.compile(
    r"^(?:(?:ARTICLE|Article|CHAPITRE|Chapitre|TITRE|Titre|SECTION|Section|ANNEXE|Annexe)\s+[\w.]+"
    r"|\d+(?:\.\d+)*)(?:\s*[.:\-–—)]\s*|\s+)\S.*$"
)
MAX_HEADING_CHARS = 100


class Chunk(BaseModel):
    index: int
    page: int | None
    section: str | None
    text: str


def detect_section(paragraph: str) -> str | None:
    """Titre de section si le paragraphe y ressemble (numérotation ou mot-clé, court, sans point final)."""
    line = paragraph.strip()
    if not line or len(line) > MAX_HEADING_CHARS or line.endswith("."):
        return None
    return line if _HEADING.match(line) else None


def _split_long(text: str, max_chars: int) -> list[str]:
    """Coupe un texte trop long aux espaces, jamais dans un mot ; un mot plus long que la limite
    reste entier."""
    pieces: list[str] = []
    words = text.split()
    current: list[str] = []
    length = 0
    for word in words:
        added = len(word) + (1 if current else 0)
        if current and length + added > max_chars:
            pieces.append(" ".join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length += added
    if current:
        pieces.append(" ".join(current))
    return pieces


def _units(paragraph: str, max_chars: int) -> list[str]:
    """Un paragraphe entier s'il tient, sinon ses phrases, elles-mêmes recoupées si nécessaire."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    units: list[str] = []
    for sentence in _SENTENCES.split(paragraph):
        sentence = sentence.strip()
        if not sentence:
            continue
        units.extend([sentence] if len(sentence) <= max_chars else _split_long(sentence, max_chars))
    return units


def _tail(text: str, overlap: int) -> str:
    """Fin de morceau réutilisée en tête du suivant, coupée à un espace."""
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    cut = text[-overlap:]
    space = cut.find(" ")
    return cut[space + 1 :] if space != -1 else cut


class _Buffer:
    """Morceau en cours de constitution sur une page : unités, longueur, section courante."""

    def __init__(self, section: str | None):
        self.units: list[str] = []
        self.length = 0
        self.section = section

    def add(self, unit: str) -> None:
        self.length += len(unit) + (1 if self.units else 0)
        self.units.append(unit)

    def fits(self, unit: str, max_chars: int) -> bool:
        return not self.units or self.length + len(unit) + 1 <= max_chars

    def text(self) -> str:
        return "\n".join(self.units)


def chunk_pages(
    pages: list[ExtractedPage], *, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP
) -> list[Chunk]:
    chunks: list[Chunk] = []
    section: str | None = None

    def emit(page_number: int, buffer: _Buffer) -> None:
        if buffer.units:
            chunks.append(
                Chunk(index=len(chunks), page=page_number, section=buffer.section, text=buffer.text())
            )

    for page in pages:
        paragraphs = [p.strip() for p in _PARAGRAPHS.split(page.text) if p.strip()]
        buffer = _Buffer(section)
        for paragraph in paragraphs:
            heading = detect_section(paragraph)
            if heading:
                emit(page.number, buffer)  # un nouveau titre ouvre un nouveau morceau
                section = heading
                buffer = _Buffer(section)
            for unit in _units(paragraph, max_chars):
                if not buffer.fits(unit, max_chars):
                    previous = buffer.text()
                    emit(page.number, buffer)
                    buffer = _Buffer(section)
                    carry = _tail(previous, overlap)
                    if carry and len(carry) + 1 + len(unit) <= max_chars:
                        buffer.add(carry)
                buffer.add(unit)
        emit(page.number, buffer)
    return chunks
