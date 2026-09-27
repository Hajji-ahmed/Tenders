"""Modèles de documents de candidature (Phase 9) : les dix plans par défaut et leur semis.

Chaque section dit ce qu'elle doit contenir, en combien de mots, et **ce qu'elle a le droit de
lire** (`requires`) : la génération ne construira son contexte qu'avec ces sources-là. Les
instructions sont écrites pour un rédacteur qui n'invente rien — ce qui manque au profil se signale
(`[À COMPLÉTER]`), il ne se comble pas.

Le semis est rejouable : un modèle déjà présent pour un type de document n'est jamais écrasé, les
plans que l'utilisateur a retouchés restent les siens."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import DocumentType, SectionSource, Template

log = get_logger("templates")

FACTS = SectionSource.company_facts.value
ANALYSIS = SectionSource.tender_analysis.value
REQUIREMENTS = SectionSource.requirements.value
ANSWERS = SectionSource.answers.value
KB = SectionSource.kb.value

NO_INVENTION = " N'avance aucun chiffre, référence ou engagement qui ne soit dans les données fournies."


def _section(key: str, title: str, instructions: str, max_words: int, requires: list[str]) -> dict:
    return {
        "key": key,
        "title": title,
        "instructions": instructions + NO_INVENTION,
        "max_words": max_words,
        "requires": requires,
    }


DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Présentation de l'entreprise",
        "document_type": DocumentType.presentation,
        "description": "Qui est l'entreprise et pourquoi elle est légitime sur cet appel d'offres.",
        "sections": [
            _section(
                "identite",
                "Identité et chiffres clés",
                "Présenter l'entreprise : raison sociale, implantation, domaines d'intervention.",
                200,
                [FACTS],
            ),
            _section(
                "expertises",
                "Secteurs et expertises",
                "Exposer les secteurs couverts, les compétences et les technologies maîtrisées.",
                250,
                [FACTS],
            ),
            _section(
                "certifications",
                "Certifications et qualifications",
                "Lister les certifications VALIDES avec leur échéance ; ne mentionner aucune "
                "certification expirée ou absente du profil.",
                150,
                [FACTS],
            ),
            _section(
                "references",
                "Références marquantes",
                "Citer les projets les plus proches de l'objet du marché : client, périmètre, résultat.",
                300,
                [FACTS, ANALYSIS],
            ),
            _section(
                "adequation",
                "Pourquoi nous pour ce marché",
                "Relier les expertises de l'entreprise aux besoins exprimés par l'appel d'offres.",
                250,
                [FACTS, ANALYSIS, REQUIREMENTS],
            ),
        ],
    },
    {
        "name": "Lettre de candidature",
        "document_type": DocumentType.lettre_candidature,
        "description": "Lettre adressée à l'organisme acheteur.",
        "sections": [
            _section(
                "objet",
                "Objet et référence",
                "Rappeler l'objet du marché, sa référence et l'organisme, en une formule d'usage.",
                120,
                [ANALYSIS],
            ),
            _section(
                "interet",
                "Déclaration d'intérêt",
                "Déclarer l'intention de soumissionner et l'intérêt de l'entreprise pour ce marché.",
                150,
                [ANALYSIS, FACTS],
            ),
            _section(
                "adequation",
                "Synthèse de l'adéquation",
                "Résumer en quelques lignes ce qui rend la candidature recevable : qualifications, "
                "références, moyens — en s'appuyant sur les exigences du règlement.",
                250,
                [FACTS, REQUIREMENTS, ANSWERS],
            ),
            _section(
                "engagements",
                "Engagements et signature",
                "Formuler les engagements demandés (délai de validité, respect du cahier des charges) "
                "et le bloc de signature ; laisser [À COMPLÉTER] pour le lieu, la date et le signataire.",
                150,
                [ANALYSIS, REQUIREMENTS],
            ),
        ],
    },
    {
        "name": "Offre technique",
        "document_type": DocumentType.offre_technique,
        "description": "Ce que l'entreprise propose de réaliser et comment.",
        "sections": [
            _section(
                "contexte",
                "Contexte et enjeux",
                "Restituer le contexte du marché et les enjeux de l'organisme, tels que le dossier les pose.",
                300,
                [ANALYSIS, KB],
            ),
            _section(
                "perimetre",
                "Périmètre proposé",
                "Délimiter la prestation : ce qui est couvert, ce qui ne l'est pas.",
                350,
                [ANALYSIS, REQUIREMENTS],
            ),
            _section(
                "solution",
                "Solution technique",
                "Décrire la solution, les moyens techniques et les technologies employées.",
                500,
                [FACTS, ANALYSIS, KB],
            ),
            _section(
                "livrables",
                "Livrables",
                "Lister les livrables attendus et leur forme, d'après le dossier de consultation.",
                250,
                [ANALYSIS],
            ),
            _section(
                "hypotheses",
                "Hypothèses et limites",
                "Énoncer les hypothèses de travail et les points restant à préciser avec l'organisme.",
                200,
                [ANALYSIS, ANSWERS],
            ),
        ],
    },
    {
        "name": "Méthodologie",
        "document_type": DocumentType.methodologie,
        "description": "La manière de conduire la mission.",
        "sections": [
            _section(
                "approche",
                "Approche générale",
                "Exposer la démarche retenue et ses principes directeurs.",
                300,
                [FACTS, ANALYSIS],
            ),
            _section(
                "phases",
                "Phases et jalons",
                "Détailler les phases, leurs livrables et les jalons de validation.",
                400,
                [ANALYSIS, REQUIREMENTS],
            ),
            _section(
                "pilotage",
                "Pilotage et qualité",
                "Décrire le pilotage, les points de suivi et les contrôles qualité.",
                300,
                [FACTS, ANALYSIS],
            ),
            _section(
                "risques",
                "Gestion des risques",
                "Identifier les risques du projet et les mesures prévues, à partir du dossier.",
                300,
                [ANALYSIS, REQUIREMENTS],
            ),
        ],
    },
    {
        "name": "Compréhension du besoin",
        "document_type": DocumentType.comprehension_besoin,
        "description": "Preuve que le besoin de l'organisme a été lu et compris.",
        "sections": [
            _section(
                "reformulation",
                "Reformulation du besoin",
                "Reformuler le besoin avec ses propres mots, sans le déformer ni l'élargir.",
                300,
                [ANALYSIS],
            ),
            _section(
                "objectifs",
                "Objectifs et résultats attendus",
                "Énoncer les objectifs poursuivis et les résultats que l'organisme attend.",
                250,
                [ANALYSIS],
            ),
            _section(
                "contraintes",
                "Contraintes identifiées",
                "Relever les contraintes du dossier : délais, normes, site, sécurité, budget.",
                250,
                [ANALYSIS, REQUIREMENTS],
            ),
            _section(
                "attention",
                "Points d'attention",
                "Signaler les points qui demandent une vigilance particulière ou une précision.",
                200,
                [ANALYSIS, REQUIREMENTS, ANSWERS],
            ),
        ],
    },
    {
        "name": "Organisation et planning",
        "document_type": DocumentType.organisation_planning,
        "description": "Qui fait quoi, quand, et sous quelle gouvernance.",
        "sections": [
            _section(
                "organisation",
                "Organisation du projet",
                "Décrire l'organisation mise en place et l'articulation des intervenants.",
                300,
                [FACTS, ANALYSIS],
            ),
            _section(
                "planning",
                "Planning macro",
                "Proposer un planning par phases sous forme de tableau Markdown (phase, durée, "
                "livrable), cohérent avec le délai d'exécution du dossier.",
                300,
                [ANALYSIS, REQUIREMENTS],
            ),
            _section(
                "charges",
                "Charge par phase",
                "Indiquer la charge prévue par phase et par profil, si les données le permettent ; "
                "sinon, écrire [À COMPLÉTER].",
                250,
                [FACTS, ANALYSIS],
            ),
            _section(
                "gouvernance",
                "Gouvernance",
                "Préciser les instances de suivi, leur fréquence et les interlocuteurs.",
                200,
                [FACTS, ANALYSIS],
            ),
        ],
    },
    {
        "name": "Équipe proposée",
        "document_type": DocumentType.equipe,
        "description": "Les moyens humains affectés à la mission.",
        "sections": [
            _section(
                "composition",
                "Composition de l'équipe",
                "Présenter l'équipe en tableau Markdown (rôle, nom, années d'expérience), à partir "
                "des experts du profil uniquement.",
                300,
                [FACTS, REQUIREMENTS],
            ),
            _section(
                "roles",
                "Rôles et responsabilités",
                "Décrire ce dont chaque profil répond dans la mission.",
                300,
                [FACTS, ANALYSIS],
            ),
            _section(
                "disponibilite",
                "Disponibilité",
                "Indiquer la disponibilité des intervenants sur la durée du marché ; écrire "
                "[À COMPLÉTER] si le profil ne le renseigne pas.",
                200,
                [FACTS, ANALYSIS],
            ),
        ],
    },
    {
        "name": "CV d'expert",
        "document_type": DocumentType.cv,
        "description": "Un CV par expert retenu pour la mission.",
        "repeat_for": "experts",
        "sections": [
            _section(
                "profil",
                "Profil",
                "Présenter l'expert : rôle, ancienneté, domaine d'intervention.",
                200,
                [FACTS],
            ),
            _section(
                "experiences",
                "Expériences pertinentes",
                "Retenir les expériences en rapport avec l'objet du marché.",
                400,
                [FACTS, ANALYSIS],
            ),
            _section(
                "competences",
                "Compétences et technologies",
                "Lister les compétences et technologies de l'expert.",
                200,
                [FACTS],
            ),
            _section(
                "certifications",
                "Certifications et formation",
                "Citer les certifications valides et la formation ; ne rien ajouter d'absent du profil.",
                150,
                [FACTS, KB],
            ),
        ],
    },
    {
        "name": "Fiche de référence",
        "document_type": DocumentType.references,
        "description": "Une fiche par projet comparable.",
        "repeat_for": "projects",
        "sections": [
            _section(
                "client",
                "Client et contexte",
                "Identifier le client, le secteur et le contexte du projet.",
                200,
                [FACTS],
            ),
            _section(
                "perimetre",
                "Périmètre et technologies",
                "Décrire ce qui a été réalisé et avec quels moyens techniques.",
                300,
                [FACTS, KB],
            ),
            _section(
                "resultats",
                "Résultats",
                "Rapporter les résultats obtenus, chiffrés seulement s'ils figurent au profil.",
                250,
                [FACTS, KB],
            ),
            _section(
                "transposition",
                "Ce que ce projet apporte à ce marché",
                "Relier cette référence aux besoins de l'appel d'offres.",
                200,
                [FACTS, ANALYSIS],
            ),
        ],
    },
    {
        "name": "Déclaration sur l'honneur",
        "document_type": DocumentType.declaration,
        "description": "Déclarations d'usage exigées par le règlement de consultation.",
        "sections": [
            _section(
                "identification",
                "Identification du candidat",
                "Reprendre l'identité de l'entreprise (raison sociale, adresse, représentant) ; "
                "écrire [À COMPLÉTER] pour toute donnée absente du profil (RC, IF, ICE, CNSS).",
                200,
                [FACTS],
            ),
            _section(
                "declarations",
                "Déclarations sur l'honneur",
                "Reprendre les déclarations exigées par le dossier (situation régulière, absence de "
                "redressement judiciaire, non-exclusion) dans les termes du règlement ; laisser "
                "[À COMPLÉTER] là où une donnée manque, ne jamais la supposer.",
                400,
                [ANALYSIS, REQUIREMENTS, ANSWERS],
            ),
            _section(
                "signature",
                "Lieu, date et signature",
                "Préparer le bloc de signature avec [À COMPLÉTER] pour le lieu, la date et le signataire.",
                100,
                [FACTS],
            ),
        ],
    },
]


def section_keys(sections: list[dict]) -> list[str]:
    return [s["key"] for s in sections]


def seed_templates(db: Session) -> list[Template]:
    """Crée les modèles par défaut manquants. Ne touche à aucun modèle existant : un plan retouché
    par l'utilisateur lui appartient. Renvoie les modèles créés (vide au second passage)."""
    existing = set(db.scalars(select(Template.document_type)))
    created: list[Template] = []
    for spec in DEFAULT_TEMPLATES:
        if spec["document_type"] in existing:
            continue
        template = Template(
            name=spec["name"],
            document_type=spec["document_type"],
            description=spec.get("description"),
            sections=spec["sections"],
            repeat_for=spec.get("repeat_for"),
            is_default=True,
            language="fr",
            version=1,
        )
        db.add(template)
        created.append(template)
    db.flush()
    if created:
        log.info("templates.seeded", created=len(created))
    return created
