"""Requêtes de recherche web dérivées d'un profil : « appel d'offres <mot-clé> <secteur> <pays> »,
produit cartésien limité, dédupliqué, dans l'ordre de saisie (les premiers mots-clés d'abord)."""

from itertools import product

from app.models import SearchProfile

TENDER_TERM = "appel d'offres"

# Codes ISO 3166-1 alpha-2 → nom français (pays cibles d'InnoSustain et francophonie) ; sinon pycountry.
COUNTRY_NAMES_FR: dict[str, str] = {
    "MA": "Maroc", "DZ": "Algérie", "TN": "Tunisie", "MR": "Mauritanie", "EG": "Égypte", "LY": "Libye",
    "SN": "Sénégal", "CI": "Côte d'Ivoire", "CM": "Cameroun", "BJ": "Bénin", "BF": "Burkina Faso",
    "ML": "Mali", "NE": "Niger", "TG": "Togo", "GA": "Gabon", "CG": "Congo", "CD": "RD Congo",
    "GN": "Guinée", "MG": "Madagascar", "TD": "Tchad", "CF": "Centrafrique", "DJ": "Djibouti",
    "KM": "Comores", "RW": "Rwanda", "BI": "Burundi", "GH": "Ghana", "NG": "Nigeria", "KE": "Kenya",
    "ET": "Éthiopie", "TZ": "Tanzanie", "ZA": "Afrique du Sud", "MU": "Maurice",
    "FR": "France", "BE": "Belgique", "CH": "Suisse", "LU": "Luxembourg", "CA": "Canada",
    "ES": "Espagne", "IT": "Italie", "DE": "Allemagne", "PT": "Portugal", "GB": "Royaume-Uni",
    "US": "États-Unis", "AE": "Émirats arabes unis", "SA": "Arabie saoudite", "QA": "Qatar",
}  # fmt: skip


def country_name(code: str) -> str:
    """Nom lisible d'un pays pour une requête ; le code lui-même si inconnu."""
    key = code.strip().upper()
    if key in COUNTRY_NAMES_FR:
        return COUNTRY_NAMES_FR[key]
    try:
        import pycountry

        found = pycountry.countries.get(alpha_2=key)
        return found.name if found else code.strip()
    except Exception:  # noqa: BLE001 — pycountry absent ou base indisponible : le code suffit
        return code.strip()


def _clean(values: list[str] | None) -> list[str]:
    """Termes non vides, dédupliqués sans tenir compte de la casse, ordre conservé."""
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        term = " ".join(v.split())
        if term and term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return out


def build_queries(profile: SearchProfile, max_queries: int = 8) -> list[str]:
    keywords = _clean(profile.keywords) or [""]
    sectors = _clean(profile.sectors) or [""]
    countries = [country_name(c) for c in _clean(profile.countries)] or [""]
    queries: list[str] = []
    seen: set[str] = set()
    for keyword, sector, country in product(keywords, sectors, countries):
        query = " ".join(part for part in (TENDER_TERM, keyword, sector, country) if part)
        if query.lower() not in seen:
            seen.add(query.lower())
            queries.append(query)
        if len(queries) >= max_queries:
            break
    return queries
