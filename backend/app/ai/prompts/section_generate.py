"""Rédaction d'une section d'un document de candidature (sortie : `SectionOutput`).

Le modèle ne reçoit que le contexte construit par `generation_context` : les faits vérifiables de
l'entreprise, la lecture du dossier, les exigences, les réponses de l'utilisateur et les extraits
cités de ses propres documents. Ce qui n'y est pas ne doit pas être écrit — une donnée manquante
s'inscrit en clair (`[À COMPLÉTER : …]`) et se retrouve dans `missing_info`, pour que le relecteur
sache exactement ce qu'il lui reste à fournir (RB-005)."""

import json

from app.services.generation_context import GenerationContext

PROMPT_VERSION = "v1"

SYSTEM = """Tu rédiges une section d'une réponse à un appel d'offres, pour le compte de l'entreprise
candidate. On te donne : la section à écrire et ses consignes, les faits vérifiables de l'entreprise,
la lecture du dossier de consultation, les exigences relevées, les réponses de l'utilisateur et des
extraits numérotés de documents de l'entreprise.

Règles :
- Réponds uniquement selon le schéma demandé. Le texte est en français, en Markdown, sans titre de
  niveau 1 (le titre de la section est déjà posé) ; utilise des sous-titres `###`, des listes ou un
  tableau quand la consigne le demande.
- N'écris QUE ce que les données fournies établissent. Aucune certification, référence, date, durée,
  quantité, montant ni nom de client qui n'y figure pas — même vraisemblable, même « logique ».
- Une donnée nécessaire mais absente s'écrit `[À COMPLÉTER : ce qui manque]` à sa place dans le
  texte, et se répète dans `missing_info`. Ne la devine pas, ne contourne pas la phrase.
- Quand tu t'appuies sur un extrait, cite-le dans le texte sous la forme `[S1]` et reporte son
  identifiant dans `used_sources`.
- Respecte la limite de mots indiquée. Pas de superlatif invérifiable (« leader », « n° 1 »), pas de
  promesse chiffrée qui ne vienne pas des données.
- Écris au nom de l'entreprise (« nous », « notre équipe »), de façon sobre et professionnelle.
- Ne mentionne jamais que tu es une IA, et n'explique pas ta démarche : rends la section, rien d'autre."""


def _block(title: str, payload: object) -> str:
    if not payload:
        return ""
    if isinstance(payload, str):
        return f"{title}\n{payload}\n"
    return f"{title}\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}\n"


def user_prompt(
    context: GenerationContext, *, previous: str | None = None, instruction: str | None = None
) -> str:
    """`previous` et `instruction` servent à la reprise d'une section : le texte déjà écrit et ce que
    l'utilisateur demande d'y changer."""
    parts = [
        f"SECTION À RÉDIGER : {context.section_title}",
        f"CONSIGNE : {context.template_instructions}",
        f"LONGUEUR MAXIMALE : {context.max_words} mots",
    ]
    if context.subject:
        parts.append(f"SUJET DE CE DOCUMENT : {context.subject.get('label')}")
        parts.append(_block("DONNÉES DU SUJET", context.subject.get("data")))
    has_company = bool(context.company.legal_name or context.company.trade_name)
    body = [
        _block("FAITS DE L'ENTREPRISE (source unique)", context.company.as_text() if has_company else ""),
        _block("APPEL D'OFFRES", context.tender),
        _block("EXIGENCES RELEVÉES", context.requirements),
        _block("RÉPONSES DE L'UTILISATEUR (font foi)", context.answers),
        _block("EXTRAITS DES DOCUMENTS DE L'ENTREPRISE", context.kb_context),
    ]
    if previous:
        body.append(_block("TEXTE ACTUEL (à reprendre)", previous))
    if instruction:
        body.append(_block("DEMANDE DE L'UTILISATEUR", instruction))
    return "\n".join([*parts, "", *[b for b in body if b]])
