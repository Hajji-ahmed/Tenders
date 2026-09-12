# Phases de développement — résumé simple

Plateforme IA de gestion des appels d'offres (« tender-ai »)
Développeur solo · 12 semaines · 13 phases

Version détaillée : [superpowers/plans/2026-09-11-plan-developpement-complet.md](superpowers/plans/2026-09-11-plan-developpement-complet.md)

---

## Vue d'ensemble

```
S1        S2          S3          S4          S5          S6
Phase 0 ► Phase 1   ► Phase 2   ► Phase 3   ► Phase 4   ► Phase 5
Cadrage   Fondations  Profil      Recherche   Dédup       Scoring
                      entreprise  & collecte              GO/NO-GO
                                                              │
S12       S11         S10         S9          S8          S7  ▼
Phase 12◄ Phase 11  ◄ Phase 9+10◄ Phase 8   ◄ Phase 7   ◄ Phase 6
Déploie-  Dashboard   Génération  Base de     Exigences   Analyse
ment      Notifs      Validation  connaiss.   Éligibilité des docs
```

Chaque phase = une tranche verticale **backend + frontend + tests** qui fonctionne toute seule.

---

## Le flux métier que l'on construit

```
Profil entreprise ──► Recherche ──► Collecte ──► Dédup ──► Score ──► GO / NO-GO
                                                                        │
Dossier prêt ◄── Validation ◄── Génération ◄── Questions ◄── Éligibilité ◄── Analyse docs
```

---

## Les 13 phases

| # | Semaine | Nom | Ce qu'on livre | Vérifiable par |
|---|---|---|---|---|
| 0 | S1 | **Cadrage** | Dépôt git, docs, modèle de données, liste des API | Les 3 PDF + docs 04/05/06 dans `docs/` |
| 1 | S2 | **Fondations** | Docker (Postgres+pgvector, Redis, MinIO), FastAPI, Next.js, login, jobs asynchrones, stockage, CI | `docker compose up` + connexion réussie |
| 2 | S3 | **Profil entreprise & documents** | Page profil (infos, compétences, technos, certifs, experts, projets, références) + upload de documents avec versions et expiration | Profil INKWAY saisi, un document expiré est marqué |
| 3 | S4 | **Recherche & collecte** | Paramètres de recherche, sources (Tavily, RSS, portails), crawler, extraction IA d'une fiche d'AO | « Lancer la recherche » crée des opportunités |
| 4 | S5 | **Normalisation & dédup** | Modèle commun, empreinte, détection de doublons (règles + fuzzy + sémantique), expiration automatique | 2 annonces du même AO = 1 seule fiche |
| 5 | S6 | **Scoring & GO/NO-GO** | Score /100 expliqué (8 critères pondérés), justification IA, décision GO/NO-GO, Kanban, historique des statuts | Chaque AO a un score + justification |
| 6 | S7 | **Analyse des documents** | Téléchargement des docs de l'AO, extraction PDF/DOCX/XLSX/TXT/ZIP, chunks + embeddings, analyse IA structurée (objet, budget, dates, critères) | Un PDF réel est analysé avec pages sources |
| 7 | S8 | **Exigences, éligibilité, questions** | Exigences `TECH-001…`, statut Conforme / À vérifier / Non conforme / Info manquante, alerte obligatoire non satisfaite, questions ciblées + réponses | Une info manquante déclenche une question |
| 8 | S9 | **Base de connaissances & RAG** | Indexation des documents entreprise, recherche interne (texte + sémantique), éligibilité étayée par des preuves documentaires | Recherche « cyber » retrouve un projet similaire |
| 9 | S10 | **Génération des documents** | 10 templates (présentation, lettre, offre technique, méthodologie, équipe, CV, références…), génération section par section avec sources, garde anti-invention, export DOCX | Documents générés avec zones `[À COMPLÉTER]` |
| 10 | S10 | **Validation humaine & versions** | Éditer / régénérer / accepter / rejeter chaque section, valider le document, versions V1…Vn, restauration, « Dossier prêt » | Rien n'est final sans validation |
| 11 | S11 | **Dashboard & notifications** | Dashboard, statistiques, notifications (AO pertinent, échéance, info manquante, certif expirée, validation requise) + email, historique, paramètres | Échéances et alertes visibles |
| 12 | S12 | **Sécurité & déploiement** | Durcissement sécurité, tests E2E du parcours complet, sauvegardes testées, Sentry, déploiement Railway staging + prod, docs finales | Application en production |

---

## Ce que chaque phase construit (vue technique)

```
Phase 1  ┌─────────────┐   ┌──────────┐   ┌────────┐   ┌────────┐
         │  Next.js    │──►│ FastAPI  │──►│Postgres│   │ Redis  │──► Workers Celery
         │  (login)    │   │ (auth)   │   │pgvector│   │ (jobs) │
         └─────────────┘   └──────────┘   └────────┘   └────────┘
                                                            + MinIO (fichiers)

Phase 2  Tables entreprise + documents            ──► pages Profil, Documents
Phase 3  Tables tenders + connecteurs (Tavily,    ──► pages Recherche, Sources, Opportunités
         crawler, RSS) + extracteur IA
Phase 4  Normaliseur + déduplicateur              ──► indicateur « N sources »
Phase 5  Moteur de score + machine à états        ──► page Détail AO, Kanban
Phase 6  Extraction texte + chunks + analyse IA   ──► onglet Analyse
Phase 7  Exigences + éligibilité + questions      ──► onglets Exigences, Questions
Phase 8  Base de connaissances (RAG)              ──► page Recherche interne, preuves
Phase 9  Templates + génération + export DOCX     ──► onglet Candidature
Phase 10 Revue par section + versions             ──► page Édition / validation
Phase 11 Notifications + dashboard + audit        ──► pages Dashboard, Stats, Historique
Phase 12 Sécurité + E2E + backups + Railway       ──► production
```

---

## Jalons de démonstration

| Jalon | Fin de | On peut montrer |
|---|---|---|
| M1 | S3 | Profil entreprise complet + documents |
| M2 | S6 | Recherche → score → décision GO/NO-GO |
| M3 | S8 | Analyse d'un dossier → exigences → questions |
| M4 | S10 | Génération → édition → validation d'un dossier |
| M5 | S12 | Application en production |

---

## Règles de travail (pour toutes les phases)

| Règle | Pourquoi |
|---|---|
| Test d'abord, puis code, puis commit | Chaque tâche est vérifiable |
| Aucun test n'appelle OpenAI ou Tavily (fakes) | Tests rapides, gratuits, stables |
| Tout service externe derrière une interface | Remplaçable sans toucher au métier |
| Toute sortie IA = schéma structuré + prompt versionné | Traçable, testable |
| Une branche par tâche → `develop` → `main` | `main` = production |

---

## Hors périmètre (V2)

Multi-utilisateurs · OCR des PDF scannés · multilingue · soumission automatique · intégrations CRM/ERP · prédiction de succès · analyse concurrentielle · Firecrawl · drag & drop Kanban.
