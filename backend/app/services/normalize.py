"""Normalisation d'un candidat avant déduplication (RB-001) : textes comparables (sans accents,
casse ni ponctuation), pays en ISO-2, devise ISO-4217, et empreinte stable `fingerprint`."""

import hashlib
import re
import unicodedata
from urllib.parse import unquote, urlparse

import pycountry

from app.ai.outputs import TenderCandidate
from app.services.query_builder import COUNTRY_NAMES_FR

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_REF_JUNK = re.compile(r"[\s\-_./\\]+")  # « AO 12/2026 » et « AO-12-2026 » = même référence

# Longueurs des colonnes `tenders` : l'extracteur peut rendre des libellés interminables (liste de
# secteurs d'un agrégateur…) ; sans borne, l'insertion échoue et toute la recherche avec.
LIMITS = {
    "title": 512,
    "organization": 255,
    "organization_type": 64,
    "reference": 128,
    "region": 128,
    "sector": 128,
    "market_type": 64,
    "norm_title": 512,
    "norm_org": 255,
    "norm_reference": 128,
}


def clip(value: str | None, limit: int) -> str | None:
    """Tronque proprement (sans espace ni séparateur final) ; None reste None."""
    if value is None or len(value) <= limit:
        return value
    return value[:limit].rstrip(" ;,-–—/|") or value[:limit]


def strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def squeeze(text: str | None) -> str:
    """Espaces compressés, extrémités nettoyées ; chaîne vide si absent."""
    return _SPACES.sub(" ", text or "").strip()


def norm_text(text: str | None) -> str:
    """Forme comparable : minuscules, sans accents ni ponctuation, espaces simples."""
    cleaned = _PUNCT.sub(" ", strip_accents(squeeze(text)).lower())
    return squeeze(cleaned)


def norm_reference(ref: str | None) -> str | None:
    """Référence comparable : majuscules, sans espaces ni séparateurs (- _ . /) ; None si vide."""
    cleaned = _REF_JUNK.sub("", strip_accents(ref or "")).upper()
    return cleaned or None


# Nom (sans accents, minuscules) → code, depuis la table FR partagée avec le constructeur de requêtes.
_FR_NAME_TO_CODE = {norm_text(name): code for code, name in COUNTRY_NAMES_FR.items()}


def country_code(value: str | None) -> str | None:
    """Code ISO 3166-1 alpha-2 depuis un code, un nom français ou un nom anglais ; None si inconnu."""
    text = squeeze(value)
    if not text:
        return None
    if len(text) == 2 and text.isalpha():
        return text.upper() if pycountry.countries.get(alpha_2=text.upper()) else None
    key = norm_text(text)
    if key in _FR_NAME_TO_CODE:
        return _FR_NAME_TO_CODE[key]
    try:
        return pycountry.countries.lookup(text).alpha_2
    except LookupError:
        return None


def currency_code(value: str | None) -> str | None:
    text = squeeze(value).upper()
    return text if len(text) == 3 and text.isalpha() else None


def document_name(url: str) -> str:
    """Nom lisible d'une pièce depuis son URL (dernier segment décodé), « document » à défaut."""
    last = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]).strip()
    return last[:255] or "document"


class NormalizedTender(TenderCandidate):
    """Candidat normalisé : mêmes champs, plus les formes comparables et l'empreinte."""

    fingerprint: str
    norm_title: str
    norm_org: str
    norm_reference: str | None


def fingerprint(norm_org: str, norm_title: str, deadline) -> str:
    raw = f"{norm_org}|{norm_title[:80]}|{deadline.isoformat() if deadline else ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:40]


def normalize(c: TenderCandidate) -> NormalizedTender:
    title = clip(squeeze(c.title), LIMITS["title"]) or ""
    organization = clip(squeeze(c.organization) or None, LIMITS["organization"])
    n_title, n_org = norm_text(title), norm_text(organization)
    data = c.model_dump()
    data.update(
        title=title,
        organization=organization,
        organization_type=clip(squeeze(c.organization_type) or None, LIMITS["organization_type"]),
        reference=clip(squeeze(c.reference) or None, LIMITS["reference"]),
        country=country_code(c.country),
        currency=currency_code(c.currency),
        description=squeeze(c.description),
        sector=clip(squeeze(c.sector) or None, LIMITS["sector"]),
        region=clip(squeeze(c.region) or None, LIMITS["region"]),
        market_type=clip(squeeze(c.market_type) or None, LIMITS["market_type"]),
        fingerprint=fingerprint(n_org, n_title, c.deadline_at),
        norm_title=clip(n_title, LIMITS["norm_title"]),
        norm_org=clip(n_org, LIMITS["norm_org"]),
        norm_reference=clip(norm_reference(c.reference), LIMITS["norm_reference"]),
    )
    return NormalizedTender(**data)


def embedding_text(n: NormalizedTender, max_description: int = 500) -> str:
    """Texte vectorisé pour la similarité sémantique : titre + début de description."""
    description = n.description[:max_description]
    return f"{n.title}\n{description}" if description else n.title
