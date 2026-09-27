"""Garde anti-invention (Phase 9) : relit le texte produit et signale ce qui ne se retrouve pas dans
les faits du profil.

Il n'empêche rien — un avertissement n'est pas un verdict, et une candidature peut légitimement
mentionner un référentiel qu'on est en train d'obtenir. Il met sous les yeux du relecteur les trois
inventions qui coûtent cher dans une réponse à appel d'offres : une certification qu'on n'a pas (ou
plus), une ancienneté gonflée, un client qu'on n'a jamais servi (RB-005)."""

import re

from rapidfuzz import fuzz

from app.services.company_facts import CompanyFacts
from app.services.normalize import norm_text

# Référentiels qu'une réponse à AO cite couramment : les voir écrits engage l'entreprise.
CERTIFICATION_PATTERNS = (
    r"ISO\s?\d{4,5}(?:[-:]\d{1,4})?",
    r"CMMI",
    r"ITIL",
    r"PMP",
    r"PRINCE2",
    r"SOC\s?2",
    r"HDS",
    r"RGS",
    r"QUALIOPI",
)
_CERTIFICATION = re.compile("|".join(CERTIFICATION_PATTERNS), re.IGNORECASE)
_YEARS = re.compile(r"(\d{1,2})\s*(?:ans|années)\b", re.IGNORECASE)
# Un nom propre composé : « Office National X », « Commune de Salé », « Société Générale ». Les
# espaces sont explicites (pas `\s`) : un titre Markdown suivi d'une phrase ne forme pas un nom —
# constaté en réel, « ### Conclusion\nNotre solution… » donnait « Conclusion Notre ».
_PROPER_NAME = re.compile(
    r"\b(?:[A-ZÉÈÊÀÂÎÔÛÇ][\wÀ-ÿ'’-]+)"
    r"(?:[ \t]+(?:de|du|des|la|le|les|d'|l'|et)?[ \t]*[A-ZÉÈÊÀÂÎÔÛÇ][\wÀ-ÿ'’-]+)+"
)
NAME_MATCH = 80  # au-delà, c'est le même client écrit autrement
# Mots qui ouvrent une phrase ou désignent l'entreprise elle-même : jamais des clients.
IGNORED_NAMES = frozenset(
    [
        "a completer", "note methodologique", "offre technique", "appel d offres", "appel d'offres",
        "cahier des charges", "reglement de consultation", "maitre d ouvrage", "maitre d'ouvrage",
        "curriculum vitae", "chef de projet", "ressources humaines",
    ]
)  # fmt: skip
# Un nom propre n'est traité comme un client que s'il désigne un organisme. Sans ce filtre, toute
# suite de mots capitalisés était suspectée — « Luminaires LED », « Attestation CNSS », un intertitre
# suivi d'une phrase… Mieux vaut manquer un client exotique que noyer le relecteur (constaté en réel).
ORGANISATION_WORDS = frozenset(
    [
        "commune", "ville", "municipalite", "prefecture", "province", "region", "wilaya", "conseil",
        "office", "agence", "ministere", "direction", "delegation", "etablissement", "administration",
        "societe", "entreprise", "groupe", "holding", "banque", "fondation", "association", "cabinet",
        "universite", "ecole", "institut", "centre", "hopital", "port", "aeroport", "onee", "ocp",
    ]
)  # fmt: skip


def _mentions(candidate: str, known: list[str]) -> bool:
    """Deux noms de clients désignent le même : « Commune de Salé » ≈ « La Commune de Salé »."""
    target = norm_text(candidate)
    return any(
        target == norm_text(k) or fuzz.token_set_ratio(target, norm_text(k)) >= NAME_MATCH for k in known
    )


def _compact(label: str) -> str:
    """Forme comparable d'un référentiel : « ISO 14001 », « iso14001 » ⇒ « iso14001 ». Pas de flou
    ici — « ISO 9001 » et « ISO 14001 » sont deux certifications, pas deux orthographes."""
    return norm_text(label).replace(" ", "").replace("-", "").replace(":", "")


def _holds_certification(cited: str, held: list[str]) -> bool:
    return any(_compact(cited) == _compact(name) for name in held)


class FactGuard:
    def __init__(self, allowed_names: list[str] | None = None):
        """`allowed_names` : noms qu'il est normal de citer sans les avoir eus pour clients —
        l'organisme acheteur, au premier chef : le document s'adresse à lui."""
        self.allowed_names = allowed_names or []

    def check(self, content_md: str, facts: CompanyFacts) -> list[str]:
        text = (content_md or "").strip()
        if not text:
            return []
        return [
            *self._certifications(text, facts),
            *self._experience(text, facts),
            *self._clients(text, facts),
        ]

    @staticmethod
    def _warn(element: str, reason: str) -> str:
        return f"Élément non vérifié : « {element} » {reason}."

    def _certifications(self, text: str, facts: CompanyFacts) -> list[str]:
        held = [c.name for c in facts.certifications]  # CompanyFacts ne contient que les valides
        seen: list[str] = []
        warnings: list[str] = []
        for match in _CERTIFICATION.finditer(text):
            cited = " ".join(match.group(0).split())
            if _holds_certification(cited, seen):
                continue
            seen.append(cited)
            if not _holds_certification(cited, held):
                warnings.append(self._warn(cited, "ne figure pas dans les certifications valides du profil"))
        return warnings

    def _experience(self, text: str, facts: CompanyFacts) -> list[str]:
        best = max((e.years_experience or 0 for e in facts.experts), default=0)
        if not best:
            return []  # rien de renseigné : aucune affirmation à contredire
        warnings: list[str] = []
        for years in {int(m.group(1)) for m in _YEARS.finditer(text)}:
            if years > best:
                warnings.append(
                    self._warn(
                        f"{years} ans",
                        f"dépasse l'ancienneté connue au profil ({best} ans pour l'expert le plus ancien)",
                    )
                )
        return warnings

    @staticmethod
    def _looks_like_an_organisation(normalized: str) -> bool:
        return any(word in ORGANISATION_WORDS for word in normalized.split())

    def _clients(self, text: str, facts: CompanyFacts) -> list[str]:
        known = (
            [p.client for p in facts.projects if p.client]
            + [p.title for p in facts.projects]
            + [r.client_name for r in facts.references]
            + [facts.legal_name, facts.trade_name or ""]
            + self.allowed_names
        )
        # Les référentiels sont retirés d'abord : « Certification ISO14001 » n'est pas un client.
        prose = _CERTIFICATION.sub(" ", text)
        seen: list[str] = []
        warnings: list[str] = []
        for match in _PROPER_NAME.finditer(prose):
            name = " ".join(match.group(0).split())
            normalized = norm_text(name)
            if normalized in IGNORED_NAMES or not self._looks_like_an_organisation(normalized):
                continue
            if _mentions(name, seen):
                continue
            seen.append(name)
            if not _mentions(name, known):
                warnings.append(self._warn(name, "ne correspond à aucun client ni projet du profil"))
        return warnings
