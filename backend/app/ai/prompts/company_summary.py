"""Résumé IA du profil de l'entreprise (sortie : texte libre, ≤ 300 mots). Le modèle ne reçoit que
`CompanyFacts` — les faits vérifiables du profil, certifications valides et documents utilisables
seulement — et il lui est interdit d'en ajouter : ce résumé sert ensuite de présentation dans le
scoring, les questions et la génération des documents de candidature."""

from app.services.company_facts import CompanyFacts

PROMPT_VERSION = "v1"
MAX_WORDS = 300

SYSTEM = f"""Tu rédiges la présentation d'une entreprise à partir de la fiche de faits qu'on te donne.

Règles :
- Écris en français, à la troisième personne, {MAX_WORDS} mots au maximum, en 2 à 4 paragraphes courts.
- N'utilise QUE les faits fournis : aucun chiffre, client, certification, technologie ou résultat qui
  n'y figure pas. Les rubriques absentes de la fiche n'existent pas : ne les comble pas et ne signale
  jamais leur absence (« l'entreprise ne mentionne pas… », « aucune certification n'est citée »).
- Pas de superlatif invérifiable (« leader », « n° 1 », « la meilleure »), pas de promesse commerciale.
- Ordre suggéré : qui est l'entreprise et où elle intervient ; ses expertises et technologies ; ses
  certifications et ses références ; ce qu'elle peut prendre en charge.
- Rends uniquement le texte du résumé, sans titre ni puces ni commentaire."""


def user_prompt(facts: CompanyFacts) -> str:
    # Sans la base documentaire (une attestation prouve une éligibilité, elle ne présente pas
    # l'entreprise) ni les rubriques vides (le modèle commentait leur absence).
    return "FAITS DU PROFIL (source unique)\n" + facts.as_text(include_documents=False, include_empty=False)
