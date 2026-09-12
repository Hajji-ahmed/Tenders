# 06 — Spécification API

Plateforme intelligente de gestion des appels d'offres · Version 1.0 · Septembre 2026

API REST servie par FastAPI. **Référence vivante : `GET /api/docs` (Swagger généré) et `GET /api/openapi.json`.** Ce document fixe les conventions et la liste des routes ; le détail des schémas est dans le code (`backend/app/schemas/`).

## Conventions

| Sujet | Règle |
|---|---|
| Base | `/api/v1` |
| Format | JSON (UTF-8) ; uploads en `multipart/form-data` |
| Auth | Cookie `access_token` (JWT HS256, `httpOnly`, `SameSite=Lax`, `Secure` en prod). Toutes les routes sauf `/health` et `/auth/login` exigent le cookie → sinon `401` |
| Rate-limit | `5/minute` sur `/auth/login`, `120/minute` global |
| Identifiants | UUID v4 |
| Dates | ISO 8601 (`2026-10-01` pour les dates, `2026-10-01T09:00:00Z` pour les horodatages, UTC) |
| Pagination | query `page` (≥ 1, défaut 1) et `size` (1–100, défaut 50) → `{"items": [...], "total": int, "page": int, "size": int}` |
| Erreurs | `{"error": {"code": "snake_case", "message": "texte lisible en français"}}` |
| Jobs longs | la route renvoie `202` avec un objet `Job` ; le client suit `GET /jobs/{id}` (`pending → running → done / failed`, `progress` 0–100, `message`, `error`, `result`) |
| Request id | en-tête `X-Request-ID` renvoyé sur chaque réponse (journalisation) |

### Codes d'erreur standards

| HTTP | `code` | Quand |
|---|---|---|
| 401 | `unauthorized`, `invalid_credentials` | Cookie absent / invalide, mauvais identifiants |
| 404 | `not_found` | Entité inconnue |
| 409 | `conflict`, `document_validated` | Doublon exact, action sur un document déjà validé |
| 422 | `validation_error`, `invalid_transition`, `sections_not_validated`, `missing_info_remaining` | Corps invalide, transition de statut interdite, validation incomplète |
| 429 | `rate_limited` | Trop de requêtes |
| 500 | `internal_error` | Erreur inattendue (détail dans Sentry, jamais dans la réponse en prod) |

## Routes

### Socle (Phase 1)

| Méthode & route | Rôle |
|---|---|
| `GET /health` | Santé (DB, Redis, stockage en Phase 12) |
| `POST /auth/login` | `{email, password}` → pose le cookie, renvoie l'utilisateur |
| `POST /auth/logout` | Supprime le cookie → `204` |
| `GET /auth/me` | Utilisateur courant |
| `GET /jobs/{id}` | Suivi d'un job |
| `GET /jobs?type=&status=` | Derniers jobs |

### Entreprise (Phase 2)

| Méthode & route | Rôle |
|---|---|
| `GET /company/profile` | Identité + profil + compteurs |
| `PUT /company/profile` | Mise à jour (champs partiels acceptés) |
| `GET /company/{skills\|technologies\|certifications\|experts\|projects\|references}` | Liste paginée |
| `POST /company/{…}` | Création → `201` |
| `GET /company/{…}/{id}` · `PATCH` · `DELETE` | Lecture, mise à jour partielle, suppression (`204`) |
| `GET /documents?category=&status=&tag=&q=&usable_only=` | Documents entreprise |
| `POST /documents` | multipart `file` + `category`, `name?`, `description?`, `issued_at?`, `expires_at?`, `tags?` (CSV) → `201` |
| `GET /documents/{id}` · `PATCH /documents/{id}` | Détail, métadonnées |
| `POST /documents/{id}/versions` | multipart `file` + `changelog?` → nouvelle version |
| `GET /documents/{id}/versions` | Historique des versions |
| `GET /documents/{id}/download` | Fichier (flux, `Content-Disposition: attachment`) |
| `DELETE /documents/{id}` | Archive (logique) → `204` |

### Recherche et opportunités (Phases 3 – 5)

| Méthode & route | Rôle |
|---|---|
| `GET/POST /search-profiles` · `GET/PATCH/DELETE /search-profiles/{id}` | Paramètres de recherche |
| `GET/POST /sources` · `GET/PATCH/DELETE /sources/{id}` | Sources d'appels d'offres |
| `POST /sources/{id}/test` | Test synchrone d'une source (3 URLs max) → rapport |
| `POST /searches` | `{search_profile_id}` → `202` Job `search_tenders` |
| `GET /searches` | Historique des recherches (jobs) |
| `GET /tenders?status=&sector=&country=&q=&deadline_before=&active_only=true&sort=created\|-created\|deadline\|-score&page=&size=` | Liste des opportunités |
| `GET /tenders/kanban` | Colonnes par statut |
| `GET /tenders/{id}` · `PATCH /tenders/{id}` | Détail, correction manuelle |
| `GET /tenders/{id}/sources` | Annonces regroupées (doublons fusionnés) |
| `GET /tenders/{id}/score` · `POST /tenders/{id}/score` | Score expliqué / recalcul (`202`) |
| `POST /tenders/{id}/decision` | `{decision: "go"\|"no_go", reason?}` |
| `POST /tenders/{id}/status` | `{status, comment?}` — transition contrôlée |
| `GET /tenders/{id}/history` | Historique des statuts |

### Analyse, exigences, questions (Phases 6 – 8)

| Méthode & route | Rôle |
|---|---|
| `GET /tenders/{id}/documents` · `POST /tenders/{id}/documents` | Documents de l'AO (liste, upload manuel) |
| `POST /tenders/{id}/documents/fetch` | Télécharge les documents détectés → `202` |
| `GET /tenders/{id}/documents/{docId}/download` | Fichier |
| `POST /tenders/{id}/analyze` | Chaîne télécharger → extraire → indexer → analyser → exigences → `202` |
| `GET /tenders/{id}/analysis` | Analyse structurée + critères |
| `GET /tenders/{id}/requirements?status=&category=&mandatory=` | Exigences `TECH-001…` |
| `PATCH /requirements/{id}` | `{status?, justification?, is_mandatory?, priority?}` |
| `POST /tenders/{id}/eligibility` · `GET /tenders/{id}/eligibility` | Évaluation (`202`) / synthèse (compteurs, ratio, obligatoires non satisfaites) |
| `GET /tenders/{id}/questions?status=` | Questions triées par priorité |
| `POST /tenders/{id}/questions/generate` | Génère les questions manquantes |
| `POST /questions/{id}/answer` · `POST /questions/{id}/skip` | `{answer}` / ignorer |
| `GET /search?q=&kinds=tenders,documents,projects,experts,references,certifications&semantic=true` | Recherche interne (texte + sémantique), résultats groupés |

### Candidature (Phases 9 – 10)

| Méthode & route | Rôle |
|---|---|
| `GET/POST /templates` · `GET/PATCH /templates/{id}` | Templates de documents |
| `POST /tenders/{id}/application` | Crée le dossier (tender en `GO`) → `201` |
| `GET /applications/{id}` | Dossier + documents + sections |
| `POST /applications/{id}/documents` | `{template_ids}` → documents à générer |
| `POST /applications/{id}/generate` | `{document_ids?}` → `202` |
| `GET /applications/{id}/documents/{docId}` | Document + sections + avertissements |
| `POST …/documents/{docId}/export` · `GET …/documents/{docId}/download` | Export DOCX / téléchargement |
| `PATCH /sections/{id}` | `{content_md?, comment?}` |
| `POST /sections/{id}/regenerate` | `{instruction?}` → `202` |
| `POST /sections/{id}/accept` · `POST /sections/{id}/reject` | Validation par section (`{comment}` pour rejet) |
| `POST /applications/{id}/documents/{docId}/validate` | Valide le document → version `Vn` (RB-006) |
| `GET …/documents/{docId}/versions` · `POST …/versions/{n}/restore` | Versions, restauration |
| `POST /applications/{id}/ready` | Dossier prêt → tender `PRET` |

### Pilotage (Phase 11)

| Méthode & route | Rôle |
|---|---|
| `GET /notifications?unread=&page=` · `POST /notifications/{id}/read` · `POST /notifications/read-all` | Notifications |
| `GET /dashboard` | Compteurs, échéances proches, valeur potentielle |
| `GET /stats?months=6` | Séries pour les graphiques |
| `GET /audit?entity_kind=&entity_id=&action=&from=&to=&page=` | Historique des actions |
| `GET /settings` · `PUT /settings` | Seuil de pertinence, email, jours d'alerte |
| `GET /settings/status` · `GET /settings/metrics` | État des intégrations, métriques des jobs |

## Exemple : lancer une recherche et suivre le job

```
POST /api/v1/searches
{"search_profile_id": "7f0c…"}

202 Accepted
{"id": "a1b2…", "type": "search_tenders", "status": "pending", "progress": 0, …}

GET /api/v1/jobs/a1b2…
{"id": "a1b2…", "status": "running", "progress": 40, "message": "Source RSS BOAMP : 12 candidats", …}

GET /api/v1/jobs/a1b2…
{"id": "a1b2…", "status": "done", "progress": 100,
 "result": {"created": 5, "merged": 2, "skipped": 3, "invalid": 1,
            "sources": {"…": {"status": "ok", "found": 7}, "…": {"status": "error", "error": "timeout"}}}}
```
