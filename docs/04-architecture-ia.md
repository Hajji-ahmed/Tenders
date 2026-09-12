# 04 — Architecture IA

Plateforme intelligente de gestion des appels d'offres · Version 1.0 · Septembre 2026

## Principes

| Principe | Application |
|---|---|
| L'IA assiste, l'humain décide | Chaque sortie IA est affichée avec la mention « Assistance IA — à vérifier » ; aucune décision ni document n'est final sans validation (RB-005, RB-006) |
| Zéro invention | Les prompts de génération n'ont accès qu'aux faits fournis (`CompanyFacts`, réponses utilisateur, extraits documentaires). Information absente ⇒ `[À COMPLÉTER : …]` (CdC §19, §39) |
| Traçabilité | Exigences, analyses et sections générées conservent la source (document, page, extrait) ; scores conservent les sous-scores |
| Sorties structurées | Chaque appel LLM renvoie un schéma Pydantic (`backend/app/ai/outputs.py`), jamais du texte libre à parser |
| Prompts versionnés | Un module par prompt dans `backend/app/ai/prompts/`, chacun avec `PROMPT_VERSION` ; la version est stockée avec le résultat |
| Fournisseurs interchangeables | `LLMProvider` et `EmbeddingProvider` sont des `Protocol` ; implémentation OpenAI + `Fake` pour les tests |
| Minimisation des données | Seuls les extraits nécessaires sont envoyés (chunks pertinents, profil résumé) — jamais les documents entiers |
| Coût maîtrisé | Deux niveaux de modèle : `fast` (extraction, scoring, questions) et `strong` (génération) ; cache des embeddings par hash de contenu |

## Pipeline documentaire

```
PDF / DOCX / XLSX / TXT / ZIP
        │
        ▼
  Stockage objet (S3 / MinIO)          ← fichier original conservé
        │
        ▼
  Extraction texte par page            ← PyMuPDF, python-docx, openpyxl
        │
        ▼
  Nettoyage + découpage en chunks      ← 1 500 caractères, recouvrement 200, page conservée
        │
        ▼
  Embeddings (1536 dims)               ← OpenAI text-embedding-3-small
        │
        ▼
  PostgreSQL + pgvector                ← table document_chunks, index HNSW cosinus
        │
        ▼
  Recherche sémantique (top-k)  ──►  Contexte RAG  ──►  LLM  ──►  Sortie structurée
```

Deux corpus **strictement séparés** par `owner_kind` :

| Corpus | Contenu | Utilisé pour |
|---|---|---|
| `tender_document` | Documents de l'appel d'offres (RC, CCTP, CCAP…) | Analyse, extraction des exigences |
| `company_document` | Documents de l'entreprise (attestations, CV, références…) | Éligibilité (preuves), génération (faits), recherche interne |

Les chunks de documents entreprise **expirés ou archivés sont exclus** de toute sélection automatique (RB-007).

## Pipeline de matching

```
Profil entreprise + Fiche AO
        │
        ▼
  Règles déterministes  ──► 8 sous-scores (0–100) × poids
        │                    secteur 20 · technologies 15 · compétences 15 · pays 10
        │                    budget 10 · expérience 15 · certifications 5 · éligibilité 10
        ▼
  Score total /100 + points forts + points faibles
        │
        ▼
  LLM (fast) : justification lisible + ajustement borné [-10, +10] motivé
        │
        ▼
  tender_scores (breakdown, justification, ai_adjustment, prompt_version)
```

Le score reste **explicable** : le breakdown est calculé par des règles ; l'IA rédige la justification et ne peut déplacer le total que de ±10 points avec une raison explicite (RB-004).

## Les 8 prompts

| # | Prompt (`app/ai/prompts/`) | Entrée | Sortie structurée (`outputs.py`) | Modèle | Phase |
|---|---|---|---|---|---|
| 1 | `tender_extract` | Texte d'une page web + liens | `TenderCandidate` (est-ce un AO ?, titre, organisme, référence, pays, budget, dates, URLs de documents, technologies, certifications requises) | fast | 3 |
| 2 | `score_assessment` | Profil résumé + fiche AO + breakdown déterministe | `ScoreAssessment` (justification, points forts, points faibles, ajustement ±10 motivé) | fast | 5 |
| 3 | `tender_analysis` | Corpus des documents de l'AO (paginé, ≤ 120 k caractères) | `TenderAnalysisOutput` (objet, organisme, budget, durée, lieu, dates clés, livrables, critères d'évaluation, documents demandés, conditions d'éligibilité, résumé — chaque élément avec page source) | fast | 6 |
| 4 | `requirements_extract` | Un document de l'AO | `RequirementsOutput` (liste de `RequirementOutput` : catégorie, description, obligatoire, preuve demandée, priorité, document + page + extrait source) | fast | 7 |
| 5 | `question_generate` | Une exigence non satisfaite + ce que l'entreprise possède déjà | `QuestionOutput` (question précise, priorité) | fast | 7 |
| 6 | `company_summary` | Faits entreprise (`CompanyFacts`) | Texte ≤ 300 mots (résumé de positionnement, sans ajout de faits) | fast | 8 |
| 7 | `eligibility_judge` | Une exigence + extraits documentaires `[S1…Sn]` | `EligibilityJudgement` (statut, justification, références de preuves) — `CONFORME` refusé sans preuve citée | fast | 8 |
| 8 | `section_generate` | Spécification de section + `GenerationContext` (faits entreprise, analyse AO, exigences, réponses, extraits `[S1…]`) | `SectionOutput` (contenu Markdown, sources utilisées, informations manquantes) | strong | 9 |

Chaque module expose : `PROMPT_VERSION: str`, `SYSTEM: str`, `user_prompt(...) -> str`.

## Garde-fous après génération

| Garde-fou | Où | Effet |
|---|---|---|
| Preuve obligatoire pour `CONFORME` | `eligibility_judge` | Sans référence `[Sn]` valide ⇒ rétrogradé en `A_VERIFIER` |
| `FactGuard` | après `section_generate` | Détecte certifications (ISO xxxx, CMMI, ITIL…), années d'expérience et clients absents des faits ⇒ avertissements affichés (non bloquant) |
| `[À COMPLÉTER]` | validation du document | Un document ne peut être validé tant qu'il en contient |
| Ajustement borné | `score_assessment` | `adjustment` ∈ [-10, +10], sinon rejeté |
| Fallback sans IA | scoring | Si le LLM échoue, le score déterministe est conservé avec une justification générée par les règles |

## Gestion des erreurs IA

| Situation | Comportement |
|---|---|
| Quota / rate-limit OpenAI | 3 tentatives avec backoff exponentiel (tenacity) |
| Réponse non conforme au schéma | Erreur journalisée, job marqué `failed` avec message lisible |
| Document illisible (PDF protégé, scan) | `extraction_status = failed`, les autres documents continuent |
| Corpus trop long | Troncature avec priorité aux documents « RC », « CCTP », « CCAP », « règlement », « cahier » |

## Tests

Aucun test n'appelle OpenAI. `FakeLLM` renvoie des sorties structurées prédéfinies et journalise chaque appel (système, utilisateur, schéma attendu, niveau) ; `FakeEmbeddings` est déterministe (hash du texte → vecteur). En environnement `test`, un `ScriptedLLM` alimente les tests de bout en bout avec des données réalistes fixes.
