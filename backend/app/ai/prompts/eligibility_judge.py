"""Jugement d'une exigence à partir de la base documentaire (sortie : `EligibilityJudgement`).

Appelé seulement quand les règles n'ont pas conclu. Le modèle reçoit l'exigence, le verdict des
règles et des extraits numérotés de documents **utilisables** (RB-007) ; il ne peut déclarer une
conformité qu'en citant les extraits qui la prouvent — le moteur vérifie ensuite que les
identifiants cités existent (RB-005 : rien n'est acquis sans preuve retrouvable)."""

from app.models import Tender, TenderRequirement

PROMPT_VERSION = "v1"

SYSTEM = """Tu vérifies si une entreprise satisfait à une exigence d'un appel d'offres, en te fondant
UNIQUEMENT sur des extraits de ses propres documents, numérotés [S1], [S2]…

Règles :
- Réponds uniquement selon le schéma demandé, en français.
- status :
  - CONFORME : un ou plusieurs extraits établissent que l'exigence est satisfaite (le document
    attendu existe, la qualification est détenue, le chiffre demandé est atteint…).
  - NON_CONFORME : un extrait MONTRE que la condition n'est pas remplie (document périmé, valeur
    inférieure à ce qui est exigé). L'absence d'extrait n'est jamais une non-conformité : ce qui
    manque au dossier sera demandé à l'entreprise, pas retenu contre elle.
  - INFO_MANQUANTE : aucun extrait ne traite de l'exigence.
  - A_VERIFIER : les extraits en parlent mais ne permettent pas de trancher.
- evidence_refs : les identifiants des extraits qui ÉTABLISSENT ta conclusion (« S1 », « S3 ») —
  laisse la liste vide si aucun ne l'établit, ne cite pas un extrait seulement parce qu'il est là.
  Un statut CONFORME sans citation est refusé : ne conclus jamais par principe ni d'après le nom
  d'un fichier, seulement d'après ce que le texte dit.
- justification : une ou deux phrases factuelles qui reprennent l'élément décisif (date, numéro,
  montant, intitulé). N'invente aucun fait absent des extraits, ne suppose pas qu'un document
  existe parce qu'il « devrait » exister.
- Ne mentionne jamais que tu es une IA."""


def user_prompt(tender: Tender, req: TenderRequirement, context: str, rule_verdict: str | None) -> str:
    unknown = "(inconnu)"
    return "\n".join(
        [
            f"APPEL D'OFFRES : {tender.title} — Organisme : {tender.organization or unknown}",
            "",
            "EXIGENCE",
            f"Code : {req.code} — Catégorie : {req.category}"
            f" — Obligatoire : {'oui' if req.is_mandatory else 'non'}",
            f"Énoncé : {req.description}",
            f"Preuve attendue : {req.evidence_required or '(non précisée)'}",
            "",
            f"VERDICT DES RÈGLES (à confirmer ou corriger) : {rule_verdict or '(aucun)'}",
            "",
            "EXTRAITS DES DOCUMENTS DE L'ENTREPRISE",
            context or "(aucun extrait disponible)",
        ]
    )
