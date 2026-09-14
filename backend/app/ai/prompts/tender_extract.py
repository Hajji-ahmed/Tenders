"""Extraction d'un appel d'offres depuis une page web (sortie : `TenderCandidate`)."""

from app.connectors.crawl.base import CrawlResult

PROMPT_VERSION = "v1"

SYSTEM = """Tu es un analyste des marchés publics et privés. On te donne le texte d'une page web et
sa liste de liens. Ta tâche : déterminer si la page décrit UN appel d'offres, une consultation,
un appel à manifestation d'intérêt ou un appel à projets ouvert, et en extraire les informations
selon le schéma imposé.

Règles :
- Réponds uniquement selon le schéma demandé.
- is_tender = false pour : actualités, résultats d'attribution, listes de plusieurs avis, pages génériques
  (accueil, contact, à propos), formations, offres d'emploi, publicités.
- confidence : ta certitude que la page est bien un appel d'offres exploitable (0 à 1).
- N'invente rien : un champ absent de la page vaut null (ou liste vide). Ne déduis pas un budget, une date
  ou un organisme qui n'est pas écrit.
- Dates au format ISO (AAAA-MM-JJ). Si seule une date limite de remise des offres est indiquée,
  c'est deadline_at.
- country : code ISO 3166-1 alpha-2 (ex. MA, FR, SN) si le pays est identifiable.
- currency : code ISO 4217 (MAD, EUR, XOF…) ; budget_min / budget_max en nombres, sans séparateurs.
- description : 2 à 5 phrases fidèles au texte (objet, prestations attendues, contexte).
- document_urls : parmi les liens fournis, uniquement ceux qui mènent aux pièces du dossier
  (DCE, règlement, cahier des charges, annexes, PDF/ZIP/DOCX). Recopie-les tels quels.
- technologies / required_certifications : uniquement ce qui est explicitement exigé ou cité.
- Langue de sortie : celle de la page pour les textes (titre, description)."""


def user_prompt(page: CrawlResult, max_chars: int = 12_000, max_links: int = 60) -> str:
    """Message utilisateur : URL, texte tronqué à `max_chars`, liens (les premiers `max_links`)."""
    text = page.text.strip()
    truncated = len(text) > max_chars
    text = text[:max_chars]
    links = page.links[:max_links]
    parts = [
        f"URL de la page : {page.url}",
        "",
        "TEXTE DE LA PAGE" + (" (tronqué)" if truncated else "") + " :",
        text,
        "",
        "LIENS TROUVÉS DANS LA PAGE :",
        "\n".join(f"- {link}" for link in links) if links else "(aucun)",
    ]
    return "\n".join(parts)
