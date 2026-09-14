# Plan de développement complet — Plateforme IA de gestion des appels d'offres (« tender-ai »)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire from scratch une application web mono-utilisateur qui recherche, collecte, déduplique, score et analyse les appels d'offres, vérifie l'éligibilité de l'entreprise, pose des questions ciblées et génère les principaux documents de candidature, avec validation humaine obligatoire.

**Architecture:** Monorepo `frontend/` (Next.js) + `backend/` (FastAPI + SQLAlchemy + Celery). PostgreSQL + pgvector est la source de vérité, Redis porte la file de jobs, un stockage objet S3-compatible (MinIO en local, Cloudflare R2 en prod) conserve les fichiers. Tout service externe (LLM, embeddings, recherche web, crawler, stockage, email) est derrière un `Protocol` Python avec une implémentation réelle et une implémentation `Fake` utilisée par les tests — aucun test n'appelle un service payant.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (sync, psycopg 3), Alembic, Pydantic v2, Celery 5 + Redis, pgvector, PyMuPDF, python-docx, openpyxl, OpenAI SDK, Tavily, httpx, BeautifulSoup, Playwright, boto3, argon2-cffi, PyJWT, structlog, rapidfuzz, pytest. Next.js 15 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query, react-hook-form + zod, Vitest, Playwright. Docker Compose, GitHub Actions, Railway, Sentry.

**Spec:** les trois documents sources (déplacés dans `docs/` par la Tâche 0.1) :
- `docs/01-cahier-des-charges.pdf` (CdC)
- `docs/02-architecture-fonctionnelle.pdf` (AF)
- `docs/03-architecture-technique.pdf` (AT)

## Global Constraints

- Un seul utilisateur principal ; pas de multi-tenant, pas de facturation, pas de gestion multi-clients (CdC §4, §5).
- Stack imposée : Next.js + TypeScript + Tailwind / FastAPI + Python / PostgreSQL + pgvector / Redis / S3 ou Cloudflare R2 / OpenAI API / Tavily ou équivalent / Firecrawl et-ou Playwright / Docker / Railway / Sentry / GitHub Actions (CdC §45, AT §4).
- Pondération du score : secteur 20 %, technologies 15 %, compétences 15 %, pays 10 %, budget 10 %, expérience 15 %, certifications 5 %, éligibilité 10 % (CdC §11, AT §13). Sous-scores et facteurs conservés.
- Statuts d'une opportunité : `NOUVEAU → A_ANALYSER → GO / NO_GO → PREPARATION → VALIDATION → PRET / SOUMIS → GAGNE / PERDU → ARCHIVE` (AF §23).
- Statuts d'une exigence : `CONFORME`, `A_VERIFIER`, `NON_CONFORME`, `INFO_MANQUANTE` (CdC §15).
- Priorités d'une question : `CRITIQUE`, `IMPORTANTE`, `FACULTATIVE` (CdC §18).
- Format d'une exigence : identifiant type `TECH-001`, description, obligatoire oui/non, preuve demandée, statut, source (document + page) (CdC §14).
- RB-001 : un même appel d'offres n'est jamais créé deux fois. RB-002 : date limite dépassée ⇒ plus proposée comme active. RB-003 : exigence obligatoire non satisfaite signalée. RB-004 : tout score IA accompagné d'une justification. RB-005 : une information IA n'est jamais automatiquement officielle. RB-006 : documents générés validés par l'utilisateur. RB-007 : documents expirés jamais sélectionnés automatiquement. RB-008 : informations sensibles protégées (CdC §33).
- L'IA n'invente aucune certification, expérience, référence ou information contractuelle (CdC §19, §39, AF §24). Informations critiques traçables vers leur source.
- Aucune soumission automatique (CdC §39).
- Traitements longs asynchrones (jobs) avec statut `pending / running / done / failed` visible dans l'UI (CdC §28, AT §5, §7).
- Chaque étape du pipeline tender possède un statut et des logs (AT §9). L'échec d'une source ou d'un document ne bloque pas les autres ; jobs idempotents (AT §25).
- Prompts, modèles et versions versionnés ; sorties IA en schémas structurés (AT §12).
- Aucune clé secrète dans Git (AT §21). HTTPS en prod, secrets en variables d'environnement, validation des uploads (taille/type) (AT §18).
- Formats documents : PDF, DOCX, XLSX, TXT, ZIP (CdC §13).
- Fichiers originaux dans le stockage objet ; PostgreSQL conserve nom, clé, taille, MIME, hash, catégorie, version, expiration, relations, statut (AT §16).
- Documentation cible : `docs/01-cahier-des-charges` … `09-plan-tests.md` (CdC §46).
- Séparation stricte données entreprise / documents des appels d'offres (AT §10, §19). Minimiser les données envoyées aux services IA externes.

---

## 0. Décisions techniques prises par ce plan

Là où la spec laisse un choix, ce plan tranche. Chaque choix est isolé derrière une interface et reste remplaçable.

| Sujet | Choix | Pourquoi |
|---|---|---|
| Workers | Celery 5 + Redis (broker + backend), Celery Beat pour les tâches planifiées | Beat nécessaire pour RB-002, expiration des documents et notifications d'échéance |
| ORM | SQLAlchemy 2.0 **synchrone** + psycopg 3 | Un seul moteur partagé par l'API (FastAPI exécute les routes `def` dans un threadpool) et les workers Celery. Mono-utilisateur ⇒ l'async DB n'apporte rien |
| Dépendances Python | `uv` + `pyproject.toml` + `uv.lock` | Rapide, reproductible |
| Auth | Email + mot de passe (argon2id) → JWT HS256 (PyJWT) dans un cookie `httpOnly` `access_token` ; rate-limit sur `/auth/login` | « Authentification forte même avec un utilisateur principal » ; cookie ⇒ pas de token exposé au JS |
| Stockage objet | MinIO en local (Docker), Cloudflare R2 en prod, boto3 derrière `StorageProvider` ; `LocalStorage` pour les tests | Même API S3 partout |
| LLM | OpenAI derrière `LLMProvider` ; deux niveaux configurables `OPENAI_MODEL_FAST` (extraction, scoring, questions) et `OPENAI_MODEL_STRONG` (génération) — vérifier les noms de modèles disponibles au moment du setup | Coût maîtrisé, interchangeable |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) derrière `EmbeddingProvider` | Compatible pgvector, économique |
| Recherche web | Tavily derrière `WebSearchProvider` | Spec |
| Crawling | `HttpxCrawler` (pages statiques) + `PlaywrightCrawler` (pages JS) derrière `CrawlerProvider` ; Firecrawl = V2 | Gratuit et auto-hébergé |
| Extraction texte | PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX), stdlib (TXT, ZIP) | Robuste, pur Python |
| Génération documentaire | Sections Markdown stockées en base → export DOCX via python-docx | Édition / validation section par section, format attendu par les AO |
| Frontend ↔ API | TanStack Query + wrapper `fetch` ; Next.js `rewrites` `/api/*` → FastAPI | Même origine ⇒ cookies simples, pas de CORS |
| UI kit | shadcn/ui (Radix + Tailwind), icônes lucide-react | Sobre, accessible, composants copiés localement |
| Tests backend | pytest + base PostgreSQL de test (`tender_test`, dans le même conteneur) + fakes de tous les services externes | Zéro appel réseau en test |
| Tests frontend | Vitest + Testing Library ; Playwright E2E en Phase 12 | |
| Dépôt | Le dossier `Tenders/` devient la racine git (nom du projet : `tender-ai`) | |

---

## 1. Structure des fichiers

```
Tenders/                                  ← racine git (« tender-ai »)
├── .github/workflows/ci.yml
├── .gitignore  .env.example  README.md
├── docker-compose.yml                    ← postgres(pgvector), redis, minio, api, worker, beat, frontend
├── docs/
│   ├── 01-cahier-des-charges.pdf         02-architecture-fonctionnelle.pdf   03-architecture-technique.pdf
│   ├── 04-architecture-ia.md  05-modele-donnees.md  06-api-specification.md
│   ├── 07-securite.md  08-deploiement.md  09-plan-tests.md
│   └── superpowers/plans/2026-09-11-plan-developpement-complet.md   ← ce fichier
├── infrastructure/
│   ├── docker/backend.Dockerfile  docker/frontend.Dockerfile
│   ├── postgres/init.sql                 ← extension vector + base tender_test
│   └── scripts/backup.sh  restore.sh
├── backend/
│   ├── pyproject.toml  uv.lock  alembic.ini  .env.example
│   ├── alembic/env.py  alembic/versions/
│   ├── app/
│   │   ├── main.py                       ← create_app()
│   │   ├── cli.py                        ← create-user, seed-templates
│   │   ├── core/
│   │   │   ├── config.py                 ← Settings (pydantic-settings)
│   │   │   ├── db.py                     ← engine, SessionLocal, get_db
│   │   │   ├── security.py               ← argon2, JWT
│   │   │   ├── deps.py                   ← get_current_user, get_llm, get_storage, …
│   │   │   ├── logging.py                ← structlog + request id
│   │   │   ├── errors.py                 ← AppError → JSON
│   │   │   └── audit.py                  ← record_audit()
│   │   ├── models/                       ← base.py user.py audit.py job.py company.py document.py
│   │   │                                    tender.py scoring.py requirement.py question.py chunk.py
│   │   │                                    template.py application.py notification.py
│   │   ├── schemas/                      ← même découpage que models/ + common.py (Page[T])
│   │   ├── repositories/                 ← accès données par agrégat
│   │   ├── services/                     ← logique métier (un module par domaine)
│   │   ├── ai/
│   │   │   ├── llm.py                    ← LLMProvider, OpenAILLM, FakeLLM
│   │   │   ├── embeddings.py             ← EmbeddingProvider, OpenAIEmbeddings, FakeEmbeddings
│   │   │   ├── outputs.py                ← schémas Pydantic des sorties structurées
│   │   │   └── prompts/                  ← un module par prompt, chacun avec PROMPT_VERSION
│   │   ├── connectors/
│   │   │   ├── search/  base.py tavily.py fake.py
│   │   │   ├── crawl/   base.py httpx_crawler.py playwright_crawler.py fake.py
│   │   │   ├── rss.py
│   │   │   ├── storage/ base.py s3.py local.py
│   │   │   └── email/   base.py resend.py fake.py
│   │   ├── workers/
│   │   │   ├── celery_app.py  tracking.py (@tracked_task)
│   │   │   └── tasks/  search.py documents.py analysis.py scoring.py eligibility.py
│   │   │               generation.py knowledge.py scheduled.py
│   │   └── api/
│   │       ├── router.py  crud_router.py  pagination.py
│   │       └── v1/  health.py auth.py jobs.py company.py documents.py search_profiles.py
│   │            sources.py searches.py tenders.py analysis.py requirements.py questions.py
│   │            search.py templates.py applications.py notifications.py dashboard.py audit.py settings.py
│   └── tests/
│       ├── conftest.py  factories.py
│       ├── unit/   api/   workers/
│       └── fixtures/  (sample.pdf, sample.docx, sample.xlsx, page_ao.html)
└── frontend/
    ├── package.json  next.config.ts  middleware.ts  vitest.config.ts
    ├── src/app/(auth)/login/page.tsx
    ├── src/app/(app)/layout.tsx          ← shell + sidebar
    ├── src/app/(app)/dashboard  company  documents  search-profiles  sources  tenders  tenders/[id]
    │            applications/[id]/documents/[docId]  search  history  stats  settings  notifications
    ├── src/lib/api.ts  src/lib/types.ts  src/lib/queries/*.ts
    ├── src/components/ui/ (shadcn)  src/components/{layout,company,tenders,documents,applications}/
    └── tests/ (vitest)  e2e/ (playwright)
```

---

## 2. Modèle de données (PostgreSQL)

Conventions : `id UUID PK DEFAULT gen_random_uuid()`, `created_at / updated_at TIMESTAMPTZ`. Enums = `String(32)` + `Enum` Python (pas d'enum PostgreSQL, pour simplifier les migrations). Les colonnes listées sont celles créées par les migrations de ce plan.

| Table | Colonnes principales | Phase |
|---|---|---|
| `users` | email (unique), password_hash, is_active, last_login_at | 1 |
| `audit_logs` | action, entity_kind, entity_id, payload JSONB, user_id, created_at | 1 |
| `jobs` | type, status(pending/running/done/failed), entity_kind, entity_id, progress, message, error, result JSONB, celery_task_id, started_at, finished_at | 1 |
| `companies` | legal_name, trade_name, description, country(ISO-2), city, address, website, email, phone, sectors TEXT[] | 2 |
| `company_profiles` | company_id (unique), positioning, ai_summary, ai_summary_updated_at | 2 |
| `skills` | company_id, name, category(expertise/service/savoir_faire), level, description | 2 |
| `technologies` | company_id, name, category(language/framework/database/cloud/tool/other), level, years_experience | 2 |
| `certifications` | company_id, name, issuer, category(technique/qualite/securite/autre), issued_at, expires_at, document_id→company_documents | 2 |
| `experts` | company_id, full_name, role, years_experience, skills TEXT[], bio, cv_document_id | 2 |
| `projects` | company_id, title, client, sector, country, start_date, end_date, budget, currency, technologies TEXT[], description, results, is_reference | 2 |
| `references` | company_id, project_id, client_name, sector, description, contact_name, contact_email, document_id | 2 |
| `company_documents` | company_id, name, category(presentation/certification/attestation/reference/cv/administratif/financier/juridique/template/autre), storage_key, mime_type, size_bytes, sha256, version, status(draft/valid/expired/archived), issued_at, expires_at, description, tags TEXT[], extraction_status, extracted_text | 2 |
| `document_versions` | document_kind(company/application), document_id, version_number, storage_key, sha256, author, changelog | 2 |
| `search_profiles` | name, countries[], regions[], sectors[], domains[], keywords[], budget_min, budget_max, currency, organization_types[], market_types[], technologies[], skills[], certifications[], experience_level, deadline_min_days, deadline_max_days, is_active, last_run_at | 3 |
| `tender_sources` | name, kind(search_engine/rss/portal/website/api), base_url, config JSONB, is_enabled, priority, last_run_at, last_status, last_error | 3 |
| `tenders` | reference, title, organization, organization_type, country, region, sector, market_type, budget_min, budget_max, currency, published_at, deadline_at, questions_deadline_at, source_url, description, summary, fingerprint (index), status, urgency, is_active, search_profile_id, raw JSONB, extra JSONB, embedding VECTOR(1536) | 3-4 |
| `tender_source_links` | tender_id, source_id, url (unique), title_seen, collected_at, raw JSONB | 3 |
| `tender_documents` | tender_id, name, source_url, storage_key, mime_type, size_bytes, sha256, download_status, extraction_status, extracted_text, page_count, error | 3/6 |
| `tender_scores` | tender_id, total, breakdown JSONB, strengths JSONB, weaknesses JSONB, justification, ai_adjustment, model, prompt_version, scoring_version, computed_at | 5 |
| `tender_decisions` | tender_id, decision(go/no_go), reason, decided_at | 5 |
| `tender_status_history` | tender_id, from_status, to_status, comment, changed_at | 5 |
| `document_chunks` | owner_kind(tender_document/company_document), owner_id, tender_id, company_document_id, chunk_index, page, section, content, embedding VECTOR(1536), token_count, metadata JSONB | 6 |
| `tender_analyses` | tender_id (unique), object, organization, reference, budget, duration, location, key_dates JSONB, deliverables JSONB, requested_documents JSONB, eligibility_conditions JSONB, summary, model, prompt_version | 6 |
| `tender_criteria` | tender_id, name, weight, description, source_page | 6 |
| `tender_requirements` | tender_id, code (TECH-001), category, description, is_mandatory, evidence_required, priority, status, justification, evidence JSONB, source_document_id, source_page, source_excerpt | 7 |
| `questions` | tender_id, requirement_id, text, priority, status(open/answered/skipped) | 7 |
| `question_answers` | question_id, answer, answered_at | 7 |
| `templates` | name, document_type, description, sections JSONB, language, version, is_default | 9 |
| `applications` | tender_id (unique), status(draft/generating/review/validated/ready/submitted/archived) | 9 |
| `application_documents` | application_id, template_id, document_type, title, status(pending/generating/draft/validated/rejected/failed), current_version, export_storage_key, warnings JSONB | 9 |
| `application_sections` | document_id, key, title, position, content_md, status(generated/edited/validated/rejected), sources JSONB, missing_info JSONB, comment, prompt_version | 9 |
| `notifications` | kind, title, body, severity(info/warning/critical), entity_kind, entity_id, is_read, read_at, emailed_at | 11 |

Ce tableau est la base de `docs/05-modele-donnees.md` (Tâche 0.1).

---

## 3. Contrats des services externes

Tous dans `backend/app/…`, définis en Phase 1 et 3, utilisés partout ensuite. Les fakes vivent à côté des implémentations réelles et sont importées par `tests/conftest.py`.

```python
# app/connectors/storage/base.py
from typing import Protocol

class StorageProvider(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...

# app/connectors/email/base.py
class EmailProvider(Protocol):
    def send(self, *, to: str, subject: str, html: str) -> None: ...

# app/ai/llm.py
from typing import Literal, Protocol, TypeVar
from pydantic import BaseModel
T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "strong"]

class LLMProvider(Protocol):
    def structured(self, *, system: str, user: str, output: type[T], tier: Tier = "fast", temperature: float = 0.0) -> T: ...
    def text(self, *, system: str, user: str, tier: Tier = "fast", temperature: float = 0.2) -> str: ...

# app/ai/embeddings.py
class EmbeddingProvider(Protocol):
    dimensions: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...

# app/connectors/search/base.py
class SearchResult(BaseModel):
    url: str; title: str; snippet: str = ""; score: float | None = None; source_name: str

class WebSearchProvider(Protocol):
    def search(self, query: str, *, max_results: int = 10, include_domains: list[str] | None = None) -> list[SearchResult]: ...

# app/connectors/crawl/base.py
class CrawlResult(BaseModel):
    url: str; status_code: int; html: str | None = None; text: str = ""; links: list[str] = []; fetched_at: datetime

class CrawlerProvider(Protocol):
    def fetch(self, url: str, *, render_js: bool = False, timeout: float = 30.0) -> CrawlResult: ...
```

---

## 4. Vue d'ensemble des phases

| Phase | Semaine (CdC §41) | Livrable testable | Dépend de |
|---|---|---|---|
| 0 — Cadrage technique | S1 (fin) | Dépôt, docs, modèle de données et API documentés | — |
| 1 — Fondations | S2 | API + front lancés en Docker, login, jobs, stockage, CI verte | 0 |
| 2 — Profil entreprise & documents | S3 | Profil complet saisi, documents uploadés/versionnés, expiration RB-007 | 1 |
| 3 — Recherche & collecte | S4 | Une recherche crée des fiches `tenders` depuis Tavily/RSS/portails | 1, 2 |
| 4 — Normalisation & déduplication | S5 | RB-001 et RB-002 garantis, sources multiples regroupées | 3 |
| 5 — Matching, scoring, GO/NO-GO | S6 | Score expliqué (RB-004), Kanban, décision GO/NO-GO, historique des statuts | 2, 4 |
| 6 — Pipeline documentaire & analyse IA | S7 | Docs PDF/DOCX/XLSX/TXT/ZIP téléchargés, extraits, chunkés, embeddés ; analyse structurée | 5 |
| 7 — Exigences, éligibilité, questions | S8 | Exigences `TECH-001…`, statuts d'éligibilité, RB-003, questions priorisées et réponses | 6 |
| 8 — Base de connaissances & RAG | S9 | KB indexée, recherche interne, éligibilité étayée par des preuves | 6, 7 |
| 9 — Génération des documents | S10 | Templates, génération section par section avec sources, export DOCX | 8 |
| 10 — Validation humaine & versions | S10 | Éditer / régénérer / accepter / rejeter / valider (RB-006), versions V1…Vn | 9 |
| 11 — Dashboard, notifications, échéances, historique | S11 | Dashboard, notifications + email, urgences, historique, statistiques | 5, 7, 10 |
| 12 — Sécurité, tests E2E, déploiement | S12 | Prod sur Railway, sauvegardes testées, Sentry, docs 07-09 | tout |

Chaque phase se termine par un logiciel fonctionnel de bout en bout sur son périmètre. Les pages frontend sont construites dans la phase de leur module (tranches verticales).

---

## 5. Récapitulatif des endpoints (base `/api/v1`)

Sert de base à `docs/06-api-specification.md`. Toutes les réponses d'erreur : `{"error": {"code": str, "message": str}}`. Listes paginées : `{"items": [...], "total": int, "page": int, "size": int}`.

| Méthode & route | Rôle | Phase |
|---|---|---|
| `GET /health` | Santé | 1 |
| `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` | Auth cookie | 1 |
| `GET /jobs/{id}` · `GET /jobs?type=&status=` | Suivi des jobs | 1 |
| `GET/PUT /company/profile` | Identité + profil | 2 |
| `GET/POST /company/{skills,technologies,certifications,experts,projects,references}` · `GET/PATCH/DELETE …/{id}` | Sous-ressources | 2 |
| `GET/POST /documents` · `GET/PATCH/DELETE /documents/{id}` · `POST /documents/{id}/versions` · `GET /documents/{id}/versions` · `GET /documents/{id}/download` | Documents entreprise | 2 |
| `GET/POST /search-profiles` · `GET/PATCH/DELETE /search-profiles/{id}` | Paramètres de recherche | 3 |
| `GET/POST /sources` · `GET/PATCH/DELETE /sources/{id}` · `POST /sources/{id}/test` | Sources | 3 |
| `POST /searches` · `GET /searches` | Lancer / lister les recherches (jobs) | 3 |
| `GET /tenders` · `GET /tenders/{id}` · `PATCH /tenders/{id}` | Opportunités | 3 |
| `GET /tenders/{id}/sources` | Annonces regroupées (doublons) | 4 |
| `GET /tenders/{id}/score` · `POST /tenders/{id}/score` | Score expliqué / recalcul | 5 |
| `POST /tenders/{id}/decision` · `POST /tenders/{id}/status` · `GET /tenders/{id}/history` | GO/NO-GO, transitions | 5 |
| `GET /tenders/kanban` | Colonnes par statut | 5 |
| `GET/POST /tenders/{id}/documents` · `GET /tenders/{id}/documents/{docId}/download` | Documents de l'AO | 6 |
| `POST /tenders/{id}/analyze` · `GET /tenders/{id}/analysis` | Analyse IA | 6 |
| `GET /tenders/{id}/requirements` · `PATCH /requirements/{id}` · `POST /tenders/{id}/eligibility` · `GET /tenders/{id}/eligibility` | Exigences & éligibilité | 7 |
| `GET /tenders/{id}/questions` · `POST /tenders/{id}/questions/generate` · `POST /questions/{id}/answer` · `POST /questions/{id}/skip` | Questions | 7 |
| `GET /search?q=&kinds=` | Recherche interne (texte + sémantique) | 8 |
| `GET/POST /templates` · `GET/PATCH /templates/{id}` | Templates | 9 |
| `POST /tenders/{id}/application` · `GET /applications/{id}` · `POST /applications/{id}/documents` · `POST /applications/{id}/generate` | Dossier de candidature | 9 |
| `GET /applications/{id}/documents/{docId}` · `POST …/export` · `GET …/download` | Documents générés | 9 |
| `PATCH /sections/{id}` · `POST /sections/{id}/regenerate` · `POST /sections/{id}/accept` · `POST /sections/{id}/reject` | Validation par section | 10 |
| `POST /applications/{id}/documents/{docId}/validate` · `GET …/versions` · `POST …/versions/{n}/restore` · `POST /applications/{id}/ready` | Validation, versions | 10 |
| `GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all` | Notifications | 11 |
| `GET /dashboard` · `GET /stats` | Dashboard, statistiques | 11 |
| `GET /audit` | Historique | 11 |
| `GET /settings` · `PUT /settings` | Seuils, email de notification | 11 |

---
# PHASE 0 — Cadrage technique (fin S1)

### Task 0.1 : Dépôt, documentation, conventions

**Files:**
- Create: `.gitignore`, `README.md`, `.env.example`, `docs/04-architecture-ia.md`, `docs/05-modele-donnees.md`, `docs/06-api-specification.md`
- Move: les trois PDF vers `docs/01-cahier-des-charges.pdf`, `docs/02-architecture-fonctionnelle.pdf`, `docs/03-architecture-technique.pdf`

**Interfaces:** aucune (documentation).

- [ ] **Step 1 : Initialiser git et déplacer les PDF**

```powershell
git init
git branch -M main
New-Item -ItemType Directory -Force docs, backend, frontend, infrastructure
Move-Item cahier_des_charges_plateforme_appels_offres_IA.pdf docs/01-cahier-des-charges.pdf
Move-Item architecture_fonctionnelle_plateforme_appels_offres_IA.pdf docs/02-architecture-fonctionnelle.pdf
Move-Item architecture_technique_plateforme_appels_offres_IA.pdf docs/03-architecture-technique.pdf
```

- [ ] **Step 2 : Écrire `.gitignore`**

```
# Python
__pycache__/  *.pyc  .venv/  .pytest_cache/  .mypy_cache/  .ruff_cache/  htmlcov/  .coverage
# Node
node_modules/  .next/  out/  coverage/
# Env & secrets
.env  .env.*  !.env.example
# Local data
data/  *.log
# OS / IDE
.DS_Store  Thumbs.db  .idea/  .vscode/
```

- [ ] **Step 3 : Écrire `.env.example`** (racine ; le backend et docker-compose le lisent)

```
APP_ENV=dev
SECRET_KEY=change-me-with-at-least-32-random-characters
DATABASE_URL=postgresql+psycopg://tender:tender@localhost:5432/tender
TEST_DATABASE_URL=postgresql+psycopg://tender:tender@localhost:5432/tender_test
REDIS_URL=redis://localhost:6379/0
STORAGE_BACKEND=s3
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_BUCKET=tender-ai
STORAGE_ACCESS_KEY=minio
STORAGE_SECRET_KEY=minio12345
OPENAI_API_KEY=
OPENAI_MODEL_FAST=gpt-4.1-mini
OPENAI_MODEL_STRONG=gpt-4.1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
TAVILY_API_KEY=
RESEND_API_KEY=
NOTIFICATION_EMAIL=
SENTRY_DSN=
API_URL=http://localhost:8000
```

- [ ] **Step 4 : Écrire `docs/05-modele-donnees.md`** — copier le tableau de la section 2 de ce plan, puis ajouter un diagramme Mermaid des relations principales :

```mermaid
erDiagram
  companies ||--|| company_profiles : has
  companies ||--o{ skills : has
  companies ||--o{ technologies : has
  companies ||--o{ certifications : has
  companies ||--o{ experts : has
  companies ||--o{ projects : has
  companies ||--o{ references : has
  companies ||--o{ company_documents : owns
  search_profiles ||--o{ tenders : produces
  tender_sources ||--o{ tender_source_links : yields
  tenders ||--o{ tender_source_links : merges
  tenders ||--o{ tender_documents : has
  tenders ||--o| tender_scores : scored
  tenders ||--o{ tender_decisions : decided
  tenders ||--o{ tender_status_history : tracks
  tenders ||--o| tender_analyses : analyzed
  tenders ||--o{ tender_criteria : has
  tenders ||--o{ tender_requirements : has
  tender_requirements ||--o{ questions : raises
  questions ||--o| question_answers : answered
  tenders ||--o| applications : prepares
  applications ||--o{ application_documents : contains
  application_documents ||--o{ application_sections : contains
  templates ||--o{ application_documents : shapes
```

- [ ] **Step 5 : Écrire `docs/06-api-specification.md`** — copier le tableau de la section 5, préciser le format d'erreur, la pagination (`page`, `size` max 100), l'auth (cookie `access_token`), et indiquer que la référence vivante est `GET /api/docs` (Swagger généré).

- [ ] **Step 6 : Écrire `docs/04-architecture-ia.md`** avec les deux pipelines du CdC §30 et la liste des prompts prévus (`tender_extract`, `tender_analysis`, `requirements_extract`, `score_assessment`, `eligibility_judge`, `question_generate`, `section_generate`, `company_summary`), chacun avec : entrée, sortie structurée (nom du schéma dans `app/ai/outputs.py`), tier de modèle, `PROMPT_VERSION`.

- [ ] **Step 7 : Écrire `README.md`** (nom du projet, objectif en 3 lignes, prérequis : Docker, uv, Node 20+, commandes `docker compose up`, `uv run pytest`, `npm run dev`, lien vers `docs/`).

- [ ] **Step 8 : Commit**

```powershell
git add -A
git commit -m "chore: init repo, docs structure, data model and API spec"
```

---

# PHASE 1 — Fondations (S2)

> **Écarts constatés à l'exécution (12/09/2026) — à respecter dans les phases suivantes :**
> - **Next.js 16** installé (pas 15) : `src/proxy.ts` remplace `middleware.ts` (même API, export `proxy`). shadcn/ui v4 style `base-nova` : composants sur Base UI, `import { cn } from "cn"` (pas de `lib/utils.ts`), pas de composant `form` (react-hook-form + `Label`/`Input` directement).
> - **PostgreSQL Docker exposé sur le port hôte 5433** (un PostgreSQL natif Windows occupe le 5432). En CI, 5432.
> - Images MinIO : `quay.io/minio/minio` et `quay.io/minio/mc` (Docker Hub `minio/*` inaccessible).
> - `Settings` lit `../.env` (racine) puis `backend/.env`.
> - Vitest en `pool: "threads"` (le pool `forks` expire sous Windows avec des espaces dans le chemin).
> - Le rate-limit du login est désactivé quand `APP_ENV=test` (`limiter.enabled`), à réactiver dans le test de la Tâche 12.1.
> - Enums Python : `enum.StrEnum` (ruff UP042) au lieu de `(str, enum.Enum)`.
> - Les modules de tâches Celery sont importés dans `app/workers/tasks/__init__.py` (remplit `REGISTRY`). **Règle d'import : les tâches importent les services, jamais l'inverse** — aucun service n'importe `app.workers.tasks` (import circulaire garanti dès la Phase 6). Le test `test_services_do_not_import_tasks` le vérifie.
> - **En test, `JobService.dispatcher` est un no-op** (le job reste `pending`) tant que la fixture `run_jobs_inline` n'est pas demandée. Le setting `CELERY_TASK_ALWAYS_EAGER` a été supprimé (inopérant avec `send_task`). Un échec de dispatch (Redis absent) marque le job `failed` et renvoie 503 `service_unavailable`.
> - **Fournisseurs injectables** : dans les services et les tâches, écrire `from app.core import deps` puis `deps.get_storage()` (idem futurs `deps.get_llm()`, `deps.get_crawler()`…) — jamais `from app.core.deps import get_storage`. Les tests injectent via `deps._storage_override` (fixture `storage`) ; suivre le même motif `_<nom>_override` pour chaque nouveau fournisseur.
> - Pas de handler `ValueError` global : lever `app.core.errors.ValidationError` (422) pour les validations métier (`validate_upload` en 2.3, `LocalStorage` reste en `ValueError` = 500). `RequestValidationError` (422) et `RateLimitExceeded` (429) suivent l'enveloppe `{"error": {...}}`.
> - Un 401 supprime le cookie (`Set-Cookie … Max-Age=0`) — indispensable pour ne pas boucler `/login ⇄ /dashboard` avec `proxy.ts`. Côté front, `api()` appelle `/auth/logout` avant de recharger sur `/login`.
> - Le rate-limit du login est keyé sur `X-Forwarded-For` (relais Next.js) et compté dans Redis hors test ; uvicorn tourne avec `--proxy-headers`.
> - `Settings` refuse en `staging|prod` : clé d'exemple, `COOKIE_SECURE=false`, stockage non-https (`_deployed_guards`). Swagger n'est servi qu'en `dev`.
> - `decode_access_token` exige `exp/iat/sub` et rejette une durée de vie > `access_token_minutes` ; `get_current_user` convertit `sub` en `UUID` (sinon 401, pas 500).
> - Moteur SQLAlchemy avec `json_serializer=default=str` (UUID/datetime dans les colonnes JSON) — `make_engine(url)` partagé par l'app et les tests. `run_job` commite dans le `try` : un commit raté = job `failed`, jamais `running` orphelin.
> - `conftest` **force** `DATABASE_URL` à la valeur de test et refuse tout `drop_all` sur une base dont le nom ne finit pas par `_test`.
> - Frontend : `<Providers>` (QueryClient + Toaster) est monté dans `app/layout.tsx` (racine) car la page login utilise `useLogin()` ; l'en-tête est dans `components/layout/Header.tsx`. `retry` uniquement sur 5xx. Le matcher de `proxy.ts` exclut les fichiers statiques. Le rewrite ne relaie que `/api/v1/*`.
> - **`API_URL` est un argument de build du frontend** (rewrites figés par `next build`) : en 12.5, une image par environnement avec `--build-arg API_URL=…`, ou remplacer le rewrite par un Route Handler `app/api/[...path]/route.ts` lisant `process.env.API_URL` au runtime.
> - CLI : `create-user --email` et `set-password --email` lisent le mot de passe depuis `TENDER_PASSWORD` ou une saisie masquée — jamais en argument (historique shell, allowlists d'outils).
> - Docker dev : ports liés à `127.0.0.1`, identifiants lus depuis `.env` (`POSTGRES_*`, `MINIO_ROOT_*`), conteneurs non-root (`app` / `node`), `.dockerignore` dans `backend/` et `frontend/`, `uv` épinglé.

### Task 1.1 : Squelette backend FastAPI + outillage

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/router.py`, `backend/app/api/v1/health.py`, `backend/tests/conftest.py`, `backend/tests/api/test_health.py`, `backend/.env.example`

**Interfaces:**
- Produces: `create_app() -> FastAPI` ; `get_settings() -> Settings` (cache) ; `Settings` avec les champs listés ci-dessous.

- [ ] **Step 1 : `pyproject.toml`**

```toml
[project]
name = "tender-ai-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30",
  "pydantic>=2.8", "pydantic-settings>=2.4",
  "sqlalchemy>=2.0.32", "psycopg[binary]>=3.2", "alembic>=1.13", "pgvector>=0.3",
  "celery[redis]>=5.4", "redis>=5.0",
  "boto3>=1.35",
  "argon2-cffi>=23.1", "pyjwt>=2.9", "slowapi>=0.1.9",
  "structlog>=24.4", "sentry-sdk[fastapi]>=2.0",
  "httpx>=0.27", "tenacity>=9.0", "beautifulsoup4>=4.12", "lxml>=5.0", "feedparser>=6.0",
  "python-multipart>=0.0.9", "filetype>=1.2",
  "pymupdf>=1.24", "python-docx>=1.1", "openpyxl>=3.1",
  "openai>=1.40", "tavily-python>=0.5", "playwright>=1.46",
  "rapidfuzz>=3.9", "python-dateutil>=2.9", "pycountry>=24.6",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=5", "ruff>=0.6", "mypy>=1.11", "freezegun>=1.5", "factory-boy>=3.3"]

[tool.ruff]
line-length = 110
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
filterwarnings = ["ignore::DeprecationWarning"]
```

- [ ] **Step 2 : `app/core/config.py`**

```python
from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "staging", "prod"] = "dev"
    secret_key: str = Field(min_length=32)
    database_url: str = "postgresql+psycopg://tender:tender@localhost:5432/tender"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: Literal["s3", "local"] = "s3"
    storage_endpoint: str = "http://localhost:9000"
    storage_bucket: str = "tender-ai"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_local_dir: str = "./data/storage"

    openai_api_key: str = ""
    openai_model_fast: str = "gpt-4.1-mini"
    openai_model_strong: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    tavily_api_key: str = ""
    resend_api_key: str = ""
    notification_email: str = ""
    sentry_dsn: str = ""

    access_token_minutes: int = 60 * 12
    cookie_secure: bool = False
    max_upload_mb: int = 50
    relevance_threshold: int = 70
    celery_task_always_eager: bool = False

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3 : `app/api/v1/health.py`, `app/api/router.py`, `app/main.py`**

```python
# app/api/v1/health.py
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# app/api/router.py
from fastapi import APIRouter
from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
```

```python
# app/main.py
from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Tender AI", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
```

- [ ] **Step 4 : Test d'abord — `tests/conftest.py` (v1) et `tests/api/test_health.py`**

```python
# tests/conftest.py
import os
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://tender:tender@localhost:5432/tender_test"))
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
```

```python
# tests/api/test_health.py
def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 5 : Installer et lancer le test**

```powershell
cd backend
uv sync --extra dev
uv run pytest -q
```
Attendu : `1 passed`.

- [ ] **Step 6 : Lint** : `uv run ruff check . ; uv run ruff format .` → aucune erreur.

- [ ] **Step 7 : Commit**

```powershell
git add backend
git commit -m "feat(backend): FastAPI skeleton, settings, health endpoint"
```

---

### Task 1.2 : Docker Compose (PostgreSQL + pgvector, Redis, MinIO) et Dockerfiles

**Files:**
- Create: `docker-compose.yml`, `infrastructure/postgres/init.sql`, `infrastructure/docker/backend.Dockerfile`

**Interfaces:**
- Produces: services `postgres:5432` (bases `tender` et `tender_test`, extension `vector`), `redis:6379`, `minio:9000` (bucket `tender-ai`).

- [ ] **Step 1 : `infrastructure/postgres/init.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE DATABASE tender_test OWNER tender;
\c tender_test
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] **Step 2 : `infrastructure/docker/backend.Dockerfile`**

```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl libmagic1 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3 : `docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_USER: tender, POSTGRES_PASSWORD: tender, POSTGRES_DB: tender }
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infrastructure/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U tender"], interval: 5s, retries: 10 }

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck: { test: ["CMD", "redis-cli", "ping"], interval: 5s, retries: 10 }

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment: { MINIO_ROOT_USER: minio, MINIO_ROOT_PASSWORD: minio12345 }
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]

  minio-init:
    image: minio/mc:latest
    depends_on: [minio]
    entrypoint: >
      /bin/sh -c "sleep 3; mc alias set local http://minio:9000 minio minio12345;
      mc mb -p local/tender-ai || true"

  api:
    build: { context: ./backend, dockerfile: ../infrastructure/docker/backend.Dockerfile }
    env_file: .env
    environment: { DATABASE_URL: "postgresql+psycopg://tender:tender@postgres:5432/tender", REDIS_URL: "redis://redis:6379/0", STORAGE_ENDPOINT: "http://minio:9000" }
    ports: ["8000:8000"]
    depends_on: { postgres: { condition: service_healthy }, redis: { condition: service_healthy } }
    volumes: [./backend:/app]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: { context: ./backend, dockerfile: ../infrastructure/docker/backend.Dockerfile }
    env_file: .env
    environment: { DATABASE_URL: "postgresql+psycopg://tender:tender@postgres:5432/tender", REDIS_URL: "redis://redis:6379/0", STORAGE_ENDPOINT: "http://minio:9000" }
    depends_on: [api]
    volumes: [./backend:/app]
    command: celery -A app.workers.celery_app:celery_app worker -l info --concurrency=2

  beat:
    build: { context: ./backend, dockerfile: ../infrastructure/docker/backend.Dockerfile }
    env_file: .env
    environment: { DATABASE_URL: "postgresql+psycopg://tender:tender@postgres:5432/tender", REDIS_URL: "redis://redis:6379/0" }
    depends_on: [worker]
    volumes: [./backend:/app]
    command: celery -A app.workers.celery_app:celery_app beat -l info

volumes: { pgdata: {}, miniodata: {} }
```
(`worker` et `beat` échoueront jusqu'à la Tâche 1.6 — c'est attendu ; démarrer avec `docker compose up postgres redis minio minio-init` d'ici là.)

- [ ] **Step 4 : Vérifier**

```powershell
Copy-Item .env.example .env
docker compose up -d postgres redis minio minio-init
docker compose exec postgres psql -U tender -d tender_test -c "select extname from pg_extension"
```
Attendu : `vector` dans la liste. `http://localhost:9001` affiche le bucket `tender-ai`.

- [ ] **Step 5 : Commit** — `git add docker-compose.yml infrastructure ; git commit -m "chore: docker compose with pgvector, redis, minio"`

---

### Task 1.3 : Base SQLAlchemy, Alembic, table `users`, fixtures DB de test

**Files:**
- Create: `backend/app/core/db.py`, `backend/app/models/__init__.py`, `backend/app/models/base.py`, `backend/app/models/user.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_users.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/unit/test_db.py`

**Interfaces:**
- Produces: `Base`, `UUIDMixin`, `TimestampMixin` ; `SessionLocal`, `get_db()` (dépendance FastAPI) ; modèle `User(email, password_hash, is_active, last_login_at)` ; fixtures `db` (session transactionnelle) et `client` (TestClient avec `get_db` surchargée).

- [ ] **Step 1 : `app/models/base.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2 : `app/models/user.py` et `app/models/__init__.py`**

```python
# app/models/user.py
from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

```python
# app/models/__init__.py  — importer ici CHAQUE modèle pour qu'Alembic les voie
from app.models.base import Base
from app.models.user import User

__all__ = ["Base", "User"]
```

- [ ] **Step 3 : `app/core/db.py`**

```python
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- [ ] **Step 4 : Alembic** — `uv run alembic init alembic`, puis remplacer `alembic/env.py` :

```python
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.config import get_settings
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Dans `alembic.ini` : `file_template = %%(rev)s_%%(slug)s` et supprimer `sqlalchemy.url`.

- [ ] **Step 5 : Générer et appliquer la migration**

```powershell
uv run alembic revision --autogenerate -m "users"
uv run alembic upgrade head
```
Attendu : fichier `alembic/versions/xxxx_users.py` ; `\dt` montre `users` et `alembic_version`.

- [ ] **Step 6 : Fixtures DB dans `tests/conftest.py`** (remplacer la fixture `client`)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def app(db):
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
```

- [ ] **Step 7 : Test `tests/unit/test_db.py`**

```python
import uuid
from app.models import User


def test_user_roundtrip(db):
    u = User(email="user@example.com", password_hash="x")
    db.add(u)
    db.flush()
    assert isinstance(u.id, uuid.UUID)
    assert db.get(User, u.id).email == "user@example.com"
```

- [ ] **Step 8 : Run** `uv run pytest -q` → `2 passed`.

- [ ] **Step 9 : Commit** — `git commit -am "feat(backend): sqlalchemy base, alembic, users table, test db fixtures"`

---

### Task 1.4 : Authentification (login / logout / me), CLI de création d'utilisateur

**Files:**
- Create: `backend/app/core/security.py`, `backend/app/core/deps.py`, `backend/app/schemas/auth.py`, `backend/app/repositories/users.py`, `backend/app/services/auth.py`, `backend/app/api/v1/auth.py`, `backend/app/cli.py`
- Modify: `backend/app/api/router.py`, `backend/app/main.py` (limiter), `backend/tests/conftest.py` (fixtures `user`, `auth_client`)
- Test: `backend/tests/unit/test_security.py`, `backend/tests/api/test_auth.py`

**Interfaces:**
- Produces: `hash_password(str) -> str`, `verify_password(str, str) -> bool`, `create_access_token(sub: str) -> str`, `decode_access_token(str) -> str` ; dépendance `get_current_user(request, db) -> User` (401 sinon) ; fixture `auth_client` (TestClient authentifié) et `user`.

- [ ] **Step 1 : Tests unitaires `tests/unit/test_security.py`**

```python
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_and_verify():
    h = hash_password("S3cret!!")
    assert h != "S3cret!!"
    assert verify_password("S3cret!!", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("user-id-123")
    assert decode_access_token(token) == "user-id-123"
```

- [ ] **Step 2 : Run** `uv run pytest tests/unit/test_security.py -q` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3 : `app/core/security.py`**

```python
from datetime import UTC, datetime, timedelta
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from app.core.config import get_settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    return str(payload["sub"])
```

- [ ] **Step 4 : Tests API `tests/api/test_auth.py`**

```python
import pytest
from app.core.security import hash_password
from app.models import User


@pytest.fixture
def user(db):
    u = User(email="admin@example.com", password_hash=hash_password("Password123!"))
    db.add(u); db.flush()
    return u


def test_login_sets_cookie(client, user):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "Password123!"})
    assert r.status_code == 200
    assert "access_token" in r.cookies
    assert r.json()["email"] == "admin@example.com"


def test_login_wrong_password(client, user):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_after_login(client, user):
    client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "Password123!"})
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200 and r.json()["email"] == "admin@example.com"


def test_logout_clears_cookie(client, user):
    client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "Password123!"})
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
```

- [ ] **Step 5 : Run** → FAIL (404).

- [ ] **Step 6 : Implémentation**

```python
# app/schemas/auth.py
from uuid import UUID
from pydantic import BaseModel, EmailStr

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    model_config = {"from_attributes": True}
```

```python
# app/repositories/users.py
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import User

def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))

def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)
```

```python
# app/core/errors.py  (créé ici, enrichi en 1.5)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class AppError(Exception):
    status_code = 400
    code = "app_error"
    def __init__(self, message: str = "", *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message or self.code
        if code: self.code = code
        if status_code: self.status_code = status_code

class NotFoundError(AppError): status_code = 404; code = "not_found"
class ConflictError(AppError): status_code = 409; code = "conflict"
class UnauthorizedError(AppError): status_code = 401; code = "unauthorized"
class ForbiddenTransition(AppError): status_code = 422; code = "invalid_transition"

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})
```

```python
# app/services/auth.py
from datetime import UTC, datetime
from sqlalchemy.orm import Session
from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models import User
from app.repositories import users as users_repo

def authenticate(db: Session, email: str, password: str) -> tuple[User, str]:
    user = users_repo.get_by_email(db, email)
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Email ou mot de passe invalide", code="invalid_credentials")
    user.last_login_at = datetime.now(UTC)
    return user, create_access_token(str(user.id))
```

```python
# app/core/deps.py
import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.models import User
from app.repositories import users as users_repo

COOKIE_NAME = "access_token"

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise UnauthorizedError("Authentification requise")
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError as e:
        raise UnauthorizedError("Session invalide ou expirée") from e
    user = users_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Utilisateur inconnu")
    return user
```

```python
# app/api/v1/auth.py
from fastapi import APIRouter, Depends, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import COOKIE_NAME, get_current_user
from app.models import User
from app.schemas.auth import LoginIn, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth")
limiter = Limiter(key_func=get_remote_address)

@router.post("/login", response_model=UserOut)
@limiter.limit("5/minute")
def login(request: Request, response: Response, body: LoginIn, db: Session = Depends(get_db)):
    user, token = auth_service.authenticate(db, body.email, body.password)
    s = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=s.cookie_secure, samesite="lax",
                        max_age=s.access_token_minutes * 60, path="/")
    return user

@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return Response(status_code=204)

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
```

Dans `app/main.py` : `app.state.limiter = limiter` et `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)` (imports depuis `slowapi`), puis `register_error_handlers(app)`. Dans `router.py` : `api_router.include_router(auth.router, tags=["auth"])`.

```python
# app/cli.py
import argparse
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User

def create_user(email: str, password: str) -> None:
    with SessionLocal() as db:
        if db.query(User).filter_by(email=email.lower()).first():
            print("Utilisateur déjà existant"); return
        db.add(User(email=email.lower(), password_hash=hash_password(password)))
        db.commit(); print(f"Utilisateur {email} créé")

if __name__ == "__main__":
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user"); c.add_argument("--email", required=True); c.add_argument("--password", required=True)
    a = p.parse_args()
    if a.cmd == "create-user": create_user(a.email, a.password)
```

- [ ] **Step 7 : Fixture partagée** — déplacer `user` dans `tests/conftest.py` et ajouter :

```python
@pytest.fixture
def auth_client(client, user):
    client.post("/api/v1/auth/login", json={"email": user.email, "password": "Password123!"})
    return client
```

- [ ] **Step 8 : Run** `uv run pytest -q` → tous verts. Créer l'utilisateur réel : `uv run python -m app.cli create-user --email n.fariss@inkway.ma --password <mdp>`.

- [ ] **Step 9 : Commit** — `git commit -am "feat(auth): argon2 + JWT cookie login, current user dependency, create-user CLI"`

---

### Task 1.5 : Logs structurés, request id, audit log

**Files:**
- Create: `backend/app/core/logging.py`, `backend/app/core/audit.py`, `backend/app/models/audit.py`, `backend/alembic/versions/0002_audit_logs.py`
- Modify: `backend/app/main.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_audit.py`

**Interfaces:**
- Produces: `record_audit(db, *, action: str, entity_kind: str, entity_id: UUID | None, payload: dict | None = None, user_id: UUID | None = None) -> AuditLog` ; `get_logger(name) -> structlog.BoundLogger` ; middleware `RequestIdMiddleware` (header `X-Request-ID`).
- Convention des actions d'audit (chaîne `domaine.verbe`) : `search.launched`, `tender.created`, `tender.merged`, `tender.scored`, `tender.decision`, `tender.status_changed`, `tender.analyzed`, `document.uploaded`, `document.versioned`, `document.archived`, `requirement.updated`, `question.answered`, `application.generated`, `section.edited`, `section.regenerated`, `application_document.validated`, `profile.updated`.

- [ ] **Step 1 : Test**

```python
from app.core.audit import record_audit
from app.models.audit import AuditLog

def test_record_audit(db, user):
    log = record_audit(db, action="tender.decision", entity_kind="tender", entity_id=None,
                       payload={"decision": "go"}, user_id=user.id)
    db.flush()
    assert db.get(AuditLog, log.id).payload == {"decision": "go"}
```

- [ ] **Step 2 : Run** → FAIL.

- [ ] **Step 3 : Implémentation**

```python
# app/models/audit.py
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDMixin

class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_kind: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    user_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# app/core/audit.py
import uuid
from sqlalchemy.orm import Session
from app.models.audit import AuditLog

def record_audit(db: Session, *, action: str, entity_kind: str, entity_id: uuid.UUID | None,
                 payload: dict | None = None, user_id: uuid.UUID | None = None) -> AuditLog:
    log = AuditLog(action=action, entity_kind=entity_kind, entity_id=entity_id, payload=payload, user_id=user_id)
    db.add(log)
    return log
```

```python
# app/core/logging.py
import logging, uuid
from contextvars import ContextVar
import structlog
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

def _add_request_id(_, __, event_dict):
    event_dict["request_id"] = request_id_var.get(); return event_dict

def configure_logging(env: str) -> None:
    renderer = structlog.dev.ConsoleRenderer() if env == "dev" else structlog.processors.JSONRenderer()
    structlog.configure(processors=[structlog.contextvars.merge_contextvars, _add_request_id,
                                    structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), renderer],
                        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))

def get_logger(name: str):
    return structlog.get_logger(name)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
```

Ajouter dans `create_app()` : `configure_logging(settings.app_env)` et `app.add_middleware(RequestIdMiddleware)`. Importer `AuditLog` dans `models/__init__.py`, générer la migration `0002_audit_logs`.

- [ ] **Step 4 : Run** → PASS. **Step 5 : Commit** `feat(core): structlog, request id middleware, audit log`.

---

### Task 1.6 : Celery, table `jobs`, suivi des jobs, endpoint `/jobs`

**Files:**
- Create: `backend/app/workers/__init__.py`, `backend/app/workers/celery_app.py`, `backend/app/workers/tracking.py`, `backend/app/workers/tasks/__init__.py`, `backend/app/workers/tasks/demo.py`, `backend/app/models/job.py`, `backend/app/schemas/job.py`, `backend/app/services/jobs.py`, `backend/app/api/v1/jobs.py`, `backend/alembic/versions/0003_jobs.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/api/router.py`, `backend/tests/conftest.py`
- Test: `backend/tests/workers/test_tracking.py`, `backend/tests/api/test_jobs.py`

**Interfaces:**
- Produces: décorateur `@tracked_task("job_type")` qui enveloppe `fn(db: Session, job: Job, **kwargs) -> dict` ; `JobService.enqueue(db, job_type: str, *, entity_kind: str | None, entity_id: UUID | None, **kwargs) -> Job` ; `JobStatus` enum ; `JobOut` schema ; fixture `run_jobs_inline` (exécute les tâches immédiatement avec la session de test).
- Chaque tâche expose `task.run_inline(db, job, **kwargs)` pour les tests.

- [ ] **Step 1 : Tests**

```python
# tests/workers/test_tracking.py
from app.models.job import Job, JobStatus
from app.services.jobs import JobService
from app.workers.tasks.demo import demo_task

def test_tracked_task_marks_done(db, run_jobs_inline):
    job = JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=2)
    db.refresh(job)
    assert job.status == JobStatus.done
    assert job.result == {"doubled": 4}
    assert job.progress == 100

def test_tracked_task_marks_failed(db, run_jobs_inline):
    job = JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=-1)
    db.refresh(job)
    assert job.status == JobStatus.failed
    assert "ValueError" in job.error
```

```python
# tests/api/test_jobs.py
from app.services.jobs import JobService

def test_get_job(auth_client, db, run_jobs_inline):
    job = JobService.enqueue(db, "demo", entity_kind=None, entity_id=None, x=3)
    r = auth_client.get(f"/api/v1/jobs/{job.id}")
    assert r.status_code == 200
    assert r.json()["status"] == "done"
```

- [ ] **Step 2 : Run** → FAIL.

- [ ] **Step 3 : Implémentation**

```python
# app/models/job.py
import enum, uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDMixin

class JobStatus(str, enum.Enum):
    pending = "pending"; running = "running"; done = "done"; failed = "failed"

class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[JobStatus] = mapped_column(String(16), default=JobStatus.pending, index=True)
    entity_kind: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    progress: Mapped[int] = mapped_column(default=0)
    message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)
    params: Mapped[dict | None] = mapped_column(JSON)
    celery_task_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

```python
# app/workers/celery_app.py
from celery import Celery
from app.core.config import get_settings

s = get_settings()
celery_app = Celery("tender_ai", broker=s.redis_url, backend=s.redis_url,
                    include=["app.workers.tasks.demo"])   # chaque phase ajoute ses modules ici
celery_app.conf.update(task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1,
                       timezone="UTC", task_time_limit=60 * 30, task_always_eager=s.celery_task_always_eager,
                       beat_schedule={})                    # rempli par les phases 2, 4, 11
```

```python
# app/workers/tracking.py
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.job import Job, JobStatus
from app.workers.celery_app import celery_app

log = get_logger("jobs")
REGISTRY: dict[str, Callable] = {}   # job_type -> fn(db, job, **kwargs)

def run_job(db, job: Job, fn: Callable, **kwargs) -> None:
    job.status = JobStatus.running; job.started_at = datetime.now(UTC); db.commit()
    try:
        result = fn(db, job, **kwargs)
        job.status = JobStatus.done; job.result = result; job.progress = 100
        log.info("job.done", type=job.type, job_id=str(job.id))
    except Exception as e:  # noqa: BLE001 — on veut journaliser tout échec
        db.rollback()
        job.status = JobStatus.failed; job.error = f"{type(e).__name__}: {e}"
        log.exception("job.failed", type=job.type, job_id=str(job.id))
    finally:
        job.finished_at = datetime.now(UTC); db.commit()

def tracked_task(job_type: str):
    def deco(fn: Callable):
        REGISTRY[job_type] = fn
        @celery_app.task(bind=True, name=f"tender_ai.{job_type}")
        def _task(self, job_id: str, **kwargs):
            with SessionLocal() as db:
                job = db.get(Job, UUID(job_id))
                job.celery_task_id = self.request.id
                run_job(db, job, fn, **kwargs)
        _task.run_inline = fn
        return _task
    return deco

def set_progress(db, job: Job, progress: int, message: str | None = None) -> None:
    job.progress = max(0, min(100, progress)); job.message = message; db.commit()
```

```python
# app/services/jobs.py
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.job import Job
from app.workers.celery_app import celery_app

class JobService:
    dispatcher = staticmethod(lambda job, kwargs: celery_app.send_task(f"tender_ai.{job.type}", args=[str(job.id)], kwargs=kwargs))

    @classmethod
    def enqueue(cls, db: Session, job_type: str, *, entity_kind: str | None, entity_id: UUID | None, **kwargs) -> Job:
        job = Job(type=job_type, entity_kind=entity_kind, entity_id=entity_id, params=kwargs)
        db.add(job); db.commit()
        cls.dispatcher(job, kwargs)
        return job

    @staticmethod
    def get(db: Session, job_id: UUID) -> Job | None:
        return db.get(Job, job_id)

    @staticmethod
    def list(db: Session, *, type: str | None = None, status: str | None = None, limit: int = 50) -> list[Job]:
        q = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if type: q = q.where(Job.type == type)
        if status: q = q.where(Job.status == status)
        return list(db.scalars(q))
```

```python
# app/workers/tasks/demo.py
from app.workers.tracking import tracked_task

@tracked_task("demo")
def demo_task(db, job, *, x: int) -> dict:
    if x < 0:
        raise ValueError("x doit être positif")
    return {"doubled": x * 2}
```

```python
# app/schemas/job.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class JobOut(BaseModel):
    id: UUID; type: str; status: str; entity_kind: str | None; entity_id: UUID | None
    progress: int; message: str | None; error: str | None; result: dict | None
    started_at: datetime | None; finished_at: datetime | None; created_at: datetime
    model_config = {"from_attributes": True}
```

```python
# app/api/v1/jobs.py
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.schemas.job import JobOut
from app.services.jobs import JobService

router = APIRouter(prefix="/jobs", dependencies=[Depends(get_current_user)])

@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    job = JobService.get(db, job_id)
    if not job: raise NotFoundError("Job introuvable")
    return job

@router.get("", response_model=list[JobOut])
def list_jobs(type: str | None = None, status: str | None = None, db: Session = Depends(get_db)):
    return JobService.list(db, type=type, status=status)
```

Fixture dans `tests/conftest.py` :

```python
@pytest.fixture
def run_jobs_inline(db, monkeypatch):
    from app.services.jobs import JobService
    from app.workers.tracking import REGISTRY, run_job
    def _dispatch(job, kwargs):
        run_job(db, job, REGISTRY[job.type], **kwargs)
    monkeypatch.setattr(JobService, "dispatcher", staticmethod(_dispatch))
```
Note : `run_job` appelle `db.commit()` ; avec la session de test en `create_savepoint`, cela commite le savepoint et la transaction externe est toujours annulée à la fin du test.

- [ ] **Step 4 : Migration `0003_jobs`, run** `uv run pytest -q` → PASS. Vérifier aussi en vrai : `docker compose up -d worker` puis dans un shell `uv run python -c "from app.core.db import SessionLocal; from app.services.jobs import JobService; db=SessionLocal(); print(JobService.enqueue(db,'demo',entity_kind=None,entity_id=None,x=5).id)"` et `GET /api/v1/jobs/{id}` → `done`.

- [ ] **Step 5 : Commit** `feat(workers): celery app, tracked jobs, /jobs endpoint`.

---

### Task 1.7 : Stockage objet (S3/MinIO + Local)

**Files:**
- Create: `backend/app/connectors/storage/base.py`, `s3.py`, `local.py`, `backend/app/core/deps.py` (ajout `get_storage`)
- Test: `backend/tests/unit/test_storage.py`

**Interfaces:**
- Produces: `StorageProvider` (section 3), `S3Storage(settings)`, `LocalStorage(root: Path)` ; `get_storage() -> StorageProvider` (choisi par `settings.storage_backend`) ; fixture `storage` (LocalStorage dans `tmp_path`) ; helper `build_key(prefix: str, sha256: str, filename: str) -> str` = `f"{prefix}/{sha256[:2]}/{sha256}{ext}"`.

- [ ] **Step 1 : Test**

```python
from app.connectors.storage.local import LocalStorage
from app.connectors.storage.base import build_key

def test_local_storage_roundtrip(tmp_path):
    st = LocalStorage(tmp_path)
    st.put("a/b/file.txt", b"hello", "text/plain")
    assert st.exists("a/b/file.txt") and st.get("a/b/file.txt") == b"hello"
    st.delete("a/b/file.txt")
    assert not st.exists("a/b/file.txt")

def test_build_key():
    assert build_key("company", "abcdef0123", "Dossier.PDF") == "company/ab/abcdef0123.pdf"
```

- [ ] **Step 2 : Run** → FAIL. **Step 3 : Implémentation**

```python
# app/connectors/storage/base.py
from pathlib import PurePosixPath
from typing import Protocol

class StorageProvider(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...

def build_key(prefix: str, sha256: str, filename: str) -> str:
    ext = PurePosixPath(filename).suffix.lower()
    return f"{prefix}/{sha256[:2]}/{sha256}{ext}"
```

```python
# app/connectors/storage/local.py
from pathlib import Path

class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents: raise ValueError("clé hors du dossier de stockage")
        return p
    def put(self, key, data, content_type):
        p = self._p(key); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    def get(self, key): return self._p(key).read_bytes()
    def delete(self, key): self._p(key).unlink(missing_ok=True)
    def exists(self, key): return self._p(key).exists()
```

```python
# app/connectors/storage/s3.py
import boto3
from botocore.exceptions import ClientError
from app.core.config import Settings

class S3Storage:
    def __init__(self, s: Settings):
        self.bucket = s.storage_bucket
        self.client = boto3.client("s3", endpoint_url=s.storage_endpoint, aws_access_key_id=s.storage_access_key,
                                   aws_secret_access_key=s.storage_secret_key, region_name="auto")
    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
    def get(self, key): return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
    def delete(self, key): self.client.delete_object(Bucket=self.bucket, Key=key)
    def exists(self, key):
        try: self.client.head_object(Bucket=self.bucket, Key=key); return True
        except ClientError: return False
```

Dans `app/core/deps.py` :

```python
from functools import lru_cache
from pathlib import Path
from app.connectors.storage.local import LocalStorage
from app.connectors.storage.s3 import S3Storage

@lru_cache
def get_storage():
    s = get_settings()
    return S3Storage(s) if s.storage_backend == "s3" else LocalStorage(Path(s.storage_local_dir))
```

Fixture `storage` dans conftest : `LocalStorage(tmp_path)` + `app.dependency_overrides[get_storage] = lambda: storage`.

- [ ] **Step 4 : Run** → PASS. **Step 5 : Commit** `feat(storage): StorageProvider with S3/MinIO and local backends`.

---

### Task 1.8 : Squelette frontend Next.js, login, shell applicatif

**Files:**
- Create: `frontend/` (create-next-app), `frontend/next.config.ts`, `frontend/middleware.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/queries/auth.ts`, `frontend/src/app/providers.tsx`, `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/components/auth/LoginForm.tsx`, `frontend/src/app/(app)/layout.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/app/(app)/dashboard/page.tsx` (placeholder « Bienvenue »), `frontend/vitest.config.ts`, `frontend/tests/LoginForm.test.tsx`, `infrastructure/docker/frontend.Dockerfile`
- Modify: `docker-compose.yml` (service `frontend`)

**Interfaces:**
- Produces: `api<T>(path, init?) -> Promise<T>` (préfixe `/api/v1`, cookies, erreurs `ApiError{status, code, message}`) ; `useMe()` ; navigation du shell : Dashboard, Opportunités, Recherche (Profils, Sources), Profil entreprise, Documents, Recherche interne, Notifications, Historique, Statistiques, Paramètres.

- [ ] **Step 1 : Créer le projet**

```powershell
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
cd frontend
npx shadcn@latest init -d
npx shadcn@latest add button input label card table badge tabs dialog form select textarea sonner dropdown-menu sheet separator skeleton progress tooltip
npm i @tanstack/react-query react-hook-form zod @hookform/resolvers lucide-react date-fns
npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 2 : `next.config.ts`** (proxy même-origine vers FastAPI)

```ts
import type { NextConfig } from "next";
const API_URL = process.env.API_URL ?? "http://localhost:8000";
const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() { return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }]; },
};
export default nextConfig;
```

- [ ] **Step 3 : `middleware.ts`**

```ts
import { NextResponse, type NextRequest } from "next/server";
export function middleware(req: NextRequest) {
  const hasToken = req.cookies.has("access_token");
  const isLogin = req.nextUrl.pathname.startsWith("/login");
  if (!hasToken && !isLogin) return NextResponse.redirect(new URL("/login", req.url));
  if (hasToken && isLogin) return NextResponse.redirect(new URL("/dashboard", req.url));
  if (req.nextUrl.pathname === "/") return NextResponse.redirect(new URL("/dashboard", req.url));
  return NextResponse.next();
}
export const config = { matcher: ["/((?!api|_next|favicon.ico).*)"] };
```

- [ ] **Step 4 : `src/lib/api.ts`**

```ts
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const res = await fetch(`/api/v1${path}`, {
    credentials: "include",
    ...init,
    headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), ...(init.headers ?? {}) },
  });
  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    location.href = "/login";
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.error?.code ?? "error", body?.error?.message ?? res.statusText);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
```

- [ ] **Step 5 : Test `tests/LoginForm.test.tsx`** (écrit avant le composant)

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LoginForm } from "@/components/auth/LoginForm";

describe("LoginForm", () => {
  it("submits email and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<LoginForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "secret123");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));
    expect(onSubmit).toHaveBeenCalledWith({ email: "a@b.com", password: "secret123" });
  });
  it("shows an error message", () => {
    render(<LoginForm onSubmit={vi.fn()} error="Identifiants invalides" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Identifiants invalides");
  });
});
```

`vitest.config.ts` : plugin react, `environment: "jsdom"`, `setupFiles: ["./tests/setup.ts"]` (importe `@testing-library/jest-dom/vitest`), alias `@` → `src`. Script `"test": "vitest run"`.

- [ ] **Step 6 : Run** `npm test` → FAIL (module introuvable).

- [ ] **Step 7 : `LoginForm.tsx`** (react-hook-form + zod, champs `email`, `password`, bouton « Se connecter », `<p role="alert">` si `error`), page `login/page.tsx` qui appelle `api("/auth/login", {method:"POST", body: JSON.stringify(values)})` puis `router.replace("/dashboard")`, et affiche `error.message` en cas d'`ApiError`.

- [ ] **Step 8 : Shell `(app)/layout.tsx`** : `<Providers>` (QueryClientProvider + `<Toaster/>`), `<Sidebar/>` (liens de la liste ci-dessus, lucide icons, lien actif via `usePathname`), header avec email de `useMe()` et bouton « Déconnexion » (`POST /auth/logout` puis `/login`). Page `dashboard/page.tsx` : titre + texte « Bienvenue » (remplacée en Phase 11).

- [ ] **Step 9 : Dockerfile front + service compose**

```dockerfile
# infrastructure/docker/frontend.Dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

```yaml
  frontend:
    build: { context: ./frontend, dockerfile: ../infrastructure/docker/frontend.Dockerfile }
    environment: { API_URL: "http://api:8000" }
    ports: ["3000:3000"]
    depends_on: [api]
```

- [ ] **Step 10 : Run** `npm test` → PASS ; `npm run lint` ; `npm run dev` puis login réel sur `http://localhost:3000/login` → redirection vers `/dashboard`, `/auth/me` renvoie l'email.

- [ ] **Step 11 : Commit** `feat(frontend): next.js shell, login, api client, sidebar`.

---

### Task 1.9 : CI GitHub Actions

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1 : Workflow**

```yaml
name: CI
on: { push: { branches: [main, "feature/**"] }, pull_request: {} }
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_USER: tender, POSTGRES_PASSWORD: tender, POSTGRES_DB: tender_test }
        ports: ["5432:5432"]
        options: --health-cmd "pg_isready -U tender" --health-interval 5s --health-retries 10
      redis: { image: redis:7-alpine, ports: ["6379:6379"] }
    env:
      APP_ENV: test
      SECRET_KEY: ci-secret-key-ci-secret-key-0123456789
      DATABASE_URL: postgresql+psycopg://tender:tender@localhost:5432/tender_test
      REDIS_URL: redis://localhost:6379/0
      STORAGE_BACKEND: local
      CELERY_TASK_ALWAYS_EAGER: "true"
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra dev
      - run: uv run ruff check . && uv run ruff format --check .
      - run: psql postgresql://tender:tender@localhost:5432/tender_test -c "CREATE EXTENSION IF NOT EXISTS vector"
      - run: uv run pytest -q --cov=app --cov-report=term-missing
  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

- [ ] **Step 2 : Push et vérifier que les deux jobs sont verts.** Commit `ci: backend and frontend pipelines`.

**Fin de Phase 1 — critères :** `docker compose up` lance tout ; login fonctionne ; `GET /jobs/{id}` suit un job réel ; CI verte.

---
# PHASE 2 — Profil entreprise & documents (S3)

> **Écarts constatés à l'exécution (14/09/2026) — à respecter dans les phases suivantes :**
> - La phase a été découpée en 7 tâches (2.1 modèles, 2.2 API profil, 2.3 service documents, 2.4 API documents, 2.5 socle frontend générique, 2.6 page profil, 2.7 page documents) ; les Tasks 2.4/2.5 ci-dessous correspondent aux 2.6/2.7 exécutées.
> - **Charte InnoSustain** (pas INKWAY) : vert `#059541` / vert encre `#047a36` (primaire), jaune `#fdcd0e` (signal : compteurs, item actif, un bouton `accent` par écran), bleu lagon `#1b6f8e` (information), sidebar vert foncé `#1f5a38`, aucun noir ; police **Inter** (le site utilise Open Sans, le brief dashboard a imposé Inter). Tokens dans `globals.css` (`--brand-*`, `.brand-hero*`, `Badge` success/warning/warning-soft/inverse/muted/info, `Card accent`, `TableHeader variant="inverse"` — une seule table par page).
> - **Base UI 1.8 émet `data-orientation`, pas `data-horizontal`/`data-vertical`** : `globals.css` déclare deux `@custom-variant` qui relient les deux, sinon les onglets shadcn s'empilent en ligne et le séparateur casse. Base UI `Button` avec `render={<a/>}` garde `role="button"` : un lien de téléchargement est une `<a>` stylée par `buttonVariants`.
> - Codes d'erreur **précis** côté API (`unsupported_file_type`, `duplicate_document`, `file_too_large`) plutôt que génériques ; l'enveloppe `{"error": {code, message}}` est relayée telle quelle dans les boîtes de dialogue (`submitError`).
> - Sous-ressources du profil via `build_crud_router(model, create, update, read, prefix=, tag=)` (32 opérations) ; côté front, un seul `ResourceTab` générique + `EntityTable`/`EntityDialog` pilotés par `FieldSpec` — une liste **requise** démarre sur sa première option (sinon le formulaire est bloqué).
> - `/company` synchronise l'onglet dans `?tab=` (`useSearchParams` sous `<Suspense>`, obligatoire au rendu statique). `/documents` garde ses filtres en état local, recherche différée 300 ms, toute mutation invalide l'arbre `["documents"]`.
> - Historique des versions : `DocumentService(..., author=user.email)` — la colonne `author` est un libellé lisible, jamais l'UUID.
> - Compte de développement : `test@innosustain.com` / `InnoSustain` (local uniquement, jamais en staging/prod). Les parcours réels sont joués avec Playwright (Chromium dans le venv backend) contre l'API Docker, via un `next start` local construit avec `API_URL=http://127.0.0.1:8010` ; **tuer le processus `node` qui écoute (pas seulement le `cmd.exe` parent)** avant un rebuild, sinon l'ancien serveur sert un chunk CSS disparu (page sans style).
> - Ports : VS Code occupe 3000/8000 sur le poste ; le fichier `ports-override.yml` (scratchpad) expose l'API sur 8010 et le frontend sur 3010.

### Task 2.1 : Modèles du domaine entreprise + migration

**Files:**
- Create: `backend/app/models/company.py`, `backend/app/models/document.py`, `backend/alembic/versions/0004_company.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_company_models.py`

**Interfaces:**
- Produces: `Company`, `CompanyProfile`, `Skill`, `Technology`, `Certification`, `Expert`, `Project`, `Reference`, `CompanyDocument`, `DocumentVersion` avec les colonnes de la section 2 ; enums `SkillCategory`, `TechnologyCategory`, `CertificationCategory`, `DocumentCategory`, `DocumentStatus`, `ExtractionStatus`, `DocumentKind` ; propriété `CompanyDocument.is_expired` et `CompanyDocument.is_usable` (= status `valid` et non expiré — utilisée partout pour RB-007) ; `Certification.is_valid` (non expirée).

- [ ] **Step 1 : Test**

```python
from datetime import date, timedelta
from app.models.company import Certification, Company
from app.models.document import CompanyDocument, DocumentCategory, DocumentStatus

def test_document_expiry(db):
    c = Company(legal_name="Innovative & Sustainable Solutions", trade_name="InnoSustain"); db.add(c); db.flush()
    d = CompanyDocument(company_id=c.id, name="Kbis", category=DocumentCategory.administratif, storage_key="k",
                        mime_type="application/pdf", size_bytes=10, sha256="a"*64, status=DocumentStatus.valid,
                        expires_at=date.today() - timedelta(days=1))
    assert d.is_expired and not d.is_usable

def test_certification_validity(db):
    c = Company(legal_name="Innovative & Sustainable Solutions", trade_name="InnoSustain"); db.add(c); db.flush()
    cert = Certification(company_id=c.id, name="ISO 27001", expires_at=date.today() + timedelta(days=30))
    assert cert.is_valid
```

- [ ] **Step 2 : Run** → FAIL. **Step 3 : Modèles** (extrait — tous les champs de la section 2 doivent être présents)

```python
# app/models/company.py
import enum, uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import ARRAY, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

class SkillCategory(str, enum.Enum): expertise = "expertise"; service = "service"; savoir_faire = "savoir_faire"
class TechnologyCategory(str, enum.Enum): language="language"; framework="framework"; database="database"; cloud="cloud"; tool="tool"; other="other"
class CertificationCategory(str, enum.Enum): technique="technique"; qualite="qualite"; securite="securite"; autre="autre"

class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(128))
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    sectors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    profile: Mapped["CompanyProfile | None"] = relationship(back_populates="company", uselist=False, cascade="all, delete-orphan")
    skills: Mapped[list["Skill"]] = relationship(cascade="all, delete-orphan")
    technologies: Mapped[list["Technology"]] = relationship(cascade="all, delete-orphan")
    certifications: Mapped[list["Certification"]] = relationship(cascade="all, delete-orphan")
    experts: Mapped[list["Expert"]] = relationship(cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(cascade="all, delete-orphan")
    references: Mapped[list["Reference"]] = relationship(cascade="all, delete-orphan")

class CompanyProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    positioning: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_summary_updated_at: Mapped[date | None]
    company: Mapped[Company] = relationship(back_populates="profile")

class Certification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "certifications"
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[CertificationCategory] = mapped_column(String(32), default=CertificationCategory.autre)
    issued_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company_documents.id", ondelete="SET NULL"))
    @property
    def is_valid(self) -> bool:
        return self.expires_at is None or self.expires_at >= date.today()

# Skill(name, category, level, description) ; Technology(name, category, level, years_experience)
# Expert(full_name, role, years_experience, skills ARRAY, bio, cv_document_id)
# Project(title, client, sector, country, start_date, end_date, budget Numeric(14,2), currency, technologies ARRAY, description, results, is_reference)
# Reference(project_id, client_name, sector, description, contact_name, contact_email, document_id)
# — mêmes conventions : company_id FK indexé, String/Text/Date/ARRAY comme ci-dessus.
```

```python
# app/models/document.py
import enum, uuid
from datetime import date
from sqlalchemy import ARRAY, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDMixin

class DocumentCategory(str, enum.Enum):
    presentation="presentation"; certification="certification"; attestation="attestation"; reference="reference"; cv="cv"
    administratif="administratif"; financier="financier"; juridique="juridique"; template="template"; autre="autre"
class DocumentStatus(str, enum.Enum): draft="draft"; valid="valid"; expired="expired"; archived="archived"
class ExtractionStatus(str, enum.Enum): pending="pending"; done="done"; failed="failed"; skipped="skipped"
class DocumentKind(str, enum.Enum): company="company"; application="application"

class CompanyDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_documents"
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[DocumentCategory] = mapped_column(String(32), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[DocumentStatus] = mapped_column(String(16), default=DocumentStatus.valid, index=True)
    issued_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(String(16), default=ExtractionStatus.pending)
    extracted_text: Mapped[str | None] = mapped_column(Text)

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at < date.today()
    @property
    def is_usable(self) -> bool:            # RB-007
        return self.status == DocumentStatus.valid and not self.is_expired

class DocumentVersion(UUIDMixin, Base):
    __tablename__ = "document_versions"
    document_kind: Mapped[DocumentKind] = mapped_column(String(16))
    document_id: Mapped[uuid.UUID] = mapped_column(index=True)
    version_number: Mapped[int]
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    author: Mapped[str | None] = mapped_column(String(255))
    changelog: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)
```

- [ ] **Step 4 : Migration** `uv run alembic revision --autogenerate -m "company"` ; `upgrade head` ; `pytest` → PASS.
- [ ] **Step 5 : Commit** `feat(company): models for company, profile, skills, technologies, certifications, experts, projects, references, documents`.

---

### Task 2.2 : Routeur CRUD générique + endpoints profil et sous-ressources

**Files:**
- Create: `backend/app/api/crud_router.py`, `backend/app/api/pagination.py`, `backend/app/schemas/common.py`, `backend/app/schemas/company.py`, `backend/app/services/company.py`, `backend/app/api/v1/company.py`
- Modify: `backend/app/api/router.py`, `backend/tests/conftest.py` (fixture `company`)
- Test: `backend/tests/api/test_company.py`

**Interfaces:**
- Produces: `CompanyService.get_or_create(db) -> Company` (entreprise unique) ; `Page[T]` ; `build_crud_router(model, create_schema, update_schema, read_schema, *, prefix, tag, order_by) -> APIRouter` ; schémas `CompanyProfileIn/Out`, `SkillIn/Out`, `TechnologyIn/Out`, `CertificationIn/Out`, `ExpertIn/Out`, `ProjectIn/Out`, `ReferenceIn/Out` ; fixture `company` (InnoSustain — « Innovative & Sustainable Solutions », 3 secteurs Environnement/Énergie/Conseil, 3 technos, 1 certif ISO 14001 valide, 1 ISO 9001 expirée, 2 projets).

- [ ] **Step 1 : Tests**

```python
def test_get_profile_creates_company(auth_client):
    r = auth_client.get("/api/v1/company/profile")
    assert r.status_code == 200 and r.json()["legal_name"] == ""

def test_put_profile(auth_client):
    body = {"legal_name": "Innovative & Sustainable Solutions", "trade_name": "InnoSustain", "country": "MA", "city": "Casablanca", "sectors": ["Environnement", "Énergie", "Conseil"], "positioning": "Solutions innovantes et durables"}
    r = auth_client.put("/api/v1/company/profile", json=body)
    assert r.status_code == 200 and r.json()["sectors"] == ["IT", "Conseil"] and r.json()["positioning"] == "ESN"

def test_skill_crud(auth_client):
    r = auth_client.post("/api/v1/company/skills", json={"name": "Data engineering", "category": "expertise"})
    assert r.status_code == 201; sid = r.json()["id"]
    assert auth_client.get("/api/v1/company/skills").json()["total"] == 1
    assert auth_client.patch(f"/api/v1/company/skills/{sid}", json={"level": "expert"}).json()["level"] == "expert"
    assert auth_client.delete(f"/api/v1/company/skills/{sid}").status_code == 204
    assert auth_client.get("/api/v1/company/skills").json()["total"] == 0

def test_certification_exposes_validity(auth_client):
    r = auth_client.post("/api/v1/company/certifications", json={"name": "ISO 9001", "expires_at": "2020-01-01"})
    assert r.json()["is_valid"] is False
```

- [ ] **Step 2 : Run** → FAIL. **Step 3 : Implémentation**

```python
# app/schemas/common.py
from typing import Generic, TypeVar
from pydantic import BaseModel
T = TypeVar("T")
class Page(BaseModel, Generic[T]):
    items: list[T]; total: int; page: int; size: int
```

```python
# app/api/pagination.py
from fastapi import Query
from pydantic import BaseModel
class PageParams(BaseModel):
    page: int = 1; size: int = 50
def page_params(page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=100)) -> PageParams:
    return PageParams(page=page, size=size)
```

```python
# app/services/company.py
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.company import Company, CompanyProfile

class CompanyService:
    @staticmethod
    def get_or_create(db: Session) -> Company:
        company = db.scalar(select(Company).limit(1))
        if company is None:
            company = Company(legal_name="", profile=CompanyProfile())
            db.add(company); db.flush()
        if company.profile is None:
            company.profile = CompanyProfile(); db.flush()
        return company
```

```python
# app/api/crud_router.py
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.pagination import PageParams, page_params
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.schemas.common import Page
from app.services.company import CompanyService

def build_crud_router(model, create_schema, update_schema, read_schema, *, prefix: str, tag: str, order_by=None) -> APIRouter:
    r = APIRouter(prefix=prefix, tags=[tag], dependencies=[Depends(get_current_user)])
    order = order_by if order_by is not None else model.created_at.desc()

    def _get(db: Session, item_id: UUID):
        obj = db.get(model, item_id)
        if obj is None: raise NotFoundError(f"{model.__name__} introuvable")
        return obj

    @r.get("", response_model=Page[read_schema])
    def list_items(p: PageParams = Depends(page_params), db: Session = Depends(get_db)):
        company = CompanyService.get_or_create(db)
        base = select(model).where(model.company_id == company.id)
        total = db.scalar(select(func.count()).select_from(base.subquery()))
        items = db.scalars(base.order_by(order).offset((p.page - 1) * p.size).limit(p.size)).all()
        return Page(items=items, total=total, page=p.page, size=p.size)

    @r.post("", response_model=read_schema, status_code=201)
    def create_item(body: create_schema, db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore[valid-type]
        company = CompanyService.get_or_create(db)
        obj = model(company_id=company.id, **body.model_dump()); db.add(obj); db.flush()
        record_audit(db, action="profile.updated", entity_kind=model.__tablename__, entity_id=obj.id, user_id=user.id)
        return obj

    @r.get("/{item_id}", response_model=read_schema)
    def get_item(item_id: UUID, db: Session = Depends(get_db)): return _get(db, item_id)

    @r.patch("/{item_id}", response_model=read_schema)
    def update_item(item_id: UUID, body: update_schema, db: Session = Depends(get_db), user=Depends(get_current_user)):  # type: ignore[valid-type]
        obj = _get(db, item_id)
        for k, v in body.model_dump(exclude_unset=True).items(): setattr(obj, k, v)
        db.flush(); record_audit(db, action="profile.updated", entity_kind=model.__tablename__, entity_id=obj.id, user_id=user.id)
        return obj

    @r.delete("/{item_id}", status_code=204)
    def delete_item(item_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
        obj = _get(db, item_id); db.delete(obj)
        record_audit(db, action="profile.updated", entity_kind=model.__tablename__, entity_id=item_id, payload={"deleted": True}, user_id=user.id)
    return r
```

```python
# app/api/v1/company.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.crud_router import build_crud_router
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.company import Certification, Expert, Project, Reference, Skill, Technology
from app.schemas.company import (CertificationIn, CertificationOut, CertificationUpdate, CompanyProfileIn, CompanyProfileOut,
                                 ExpertIn, ExpertOut, ExpertUpdate, ProjectIn, ProjectOut, ProjectUpdate, ReferenceIn, ReferenceOut,
                                 ReferenceUpdate, SkillIn, SkillOut, SkillUpdate, TechnologyIn, TechnologyOut, TechnologyUpdate)
from app.services.company import CompanyService

router = APIRouter(prefix="/company", tags=["company"], dependencies=[Depends(get_current_user)])

@router.get("/profile", response_model=CompanyProfileOut)
def get_profile(db: Session = Depends(get_db)):
    c = CompanyService.get_or_create(db)
    return CompanyProfileOut.from_company(c)

@router.put("/profile", response_model=CompanyProfileOut)
def put_profile(body: CompanyProfileIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = CompanyService.get_or_create(db)
    data = body.model_dump(exclude_unset=True); positioning = data.pop("positioning", None)
    for k, v in data.items(): setattr(c, k, v)
    if positioning is not None: c.profile.positioning = positioning
    db.flush(); record_audit(db, action="profile.updated", entity_kind="company", entity_id=c.id, user_id=user.id)
    return CompanyProfileOut.from_company(c)

for model, cin, cup, cout, name in [
    (Skill, SkillIn, SkillUpdate, SkillOut, "skills"), (Technology, TechnologyIn, TechnologyUpdate, TechnologyOut, "technologies"),
    (Certification, CertificationIn, CertificationUpdate, CertificationOut, "certifications"), (Expert, ExpertIn, ExpertUpdate, ExpertOut, "experts"),
    (Project, ProjectIn, ProjectUpdate, ProjectOut, "projects"), (Reference, ReferenceIn, ReferenceUpdate, ReferenceOut, "references"),
]:
    router.include_router(build_crud_router(model, cin, cup, cout, prefix=f"/{name}", tag="company"))
```

`app/schemas/company.py` : pour chaque entité, `XxxIn` (champs requis : `name`/`title`/`full_name`/`client_name`), `XxxUpdate` (tous optionnels), `XxxOut` (`from_attributes`, + `is_valid: bool` pour `CertificationOut`). `CompanyProfileOut` = champs `Company` + `positioning` + `ai_summary` + `counts: dict[str,int]` (skills, technologies, certifications, experts, projects, references, documents) avec `@classmethod from_company(c)`.

- [ ] **Step 4 : Fixture `company`** dans conftest (crée InnoSustain avec les données citées dans Interfaces via les modèles, `db.flush()`). **Run** → PASS.
- [ ] **Step 5 : Commit** `feat(company): profile endpoint and generic CRUD for sub-resources`.

---

### Task 2.3 : Documents de l'entreprise (upload, versions, expiration RB-007)

**Files:**
- Create: `backend/app/services/documents.py`, `backend/app/schemas/document.py`, `backend/app/api/v1/documents.py`, `backend/app/workers/tasks/scheduled.py`, `backend/tests/fixtures/sample.pdf` (1 page « Attestation fiscale InnoSustain 2026 »), `sample.docx`, `sample.xlsx`, `sample.txt`
- Modify: `backend/app/api/router.py`, `backend/app/workers/celery_app.py` (include `scheduled`, beat), `backend/app/core/config.py` (`allowed_upload_mimes`)
- Test: `backend/tests/unit/test_documents_service.py`, `backend/tests/api/test_documents.py`

**Interfaces:**
- Produces: `DocumentService(db, storage)` avec `upload(*, filename, data, content_type, category, **meta) -> CompanyDocument` (valide type/taille, calcule sha256, refuse un doublon exact sha256+category avec `ConflictError`, stocke sous `build_key("company", sha, filename)`, crée `DocumentVersion` n°1, audit `document.uploaded`) ; `new_version(doc, *, filename, data, content_type, changelog) -> CompanyDocument` (version+1, ancienne clé archivée dans `DocumentVersion`) ; `archive(doc)` ; `refresh_expiry_statuses(db) -> int` (passe `valid → expired` quand `expires_at < today`) ; `ALLOWED_MIMES = {pdf, docx, xlsx, txt, zip}` ; tâche beat `refresh_document_expiry` quotidienne 01:00 UTC.
- Endpoints : voir section 5 (Phase 2).

- [ ] **Step 1 : Tests (extraits)**

```python
# tests/unit/test_documents_service.py
import pytest
from datetime import date, timedelta
from app.core.errors import ConflictError
from app.models.document import DocumentCategory, DocumentStatus
from app.services.documents import DocumentService, refresh_expiry_statuses

def test_upload_and_version(db, company, storage):
    svc = DocumentService(db, storage)
    doc = svc.upload(filename="kbis.pdf", data=b"%PDF-1.4 v1", content_type="application/pdf", category=DocumentCategory.administratif)
    assert doc.version == 1 and storage.exists(doc.storage_key)
    doc = svc.new_version(doc, filename="kbis.pdf", data=b"%PDF-1.4 v2", content_type="application/pdf", changelog="MAJ")
    assert doc.version == 2 and len(svc.versions(doc)) == 2

def test_upload_rejects_duplicate_and_bad_type(db, company, storage):
    svc = DocumentService(db, storage)
    svc.upload(filename="a.pdf", data=b"same", content_type="application/pdf", category=DocumentCategory.autre)
    with pytest.raises(ConflictError): svc.upload(filename="b.pdf", data=b"same", content_type="application/pdf", category=DocumentCategory.autre)
    with pytest.raises(ValueError): svc.upload(filename="x.exe", data=b"MZ", content_type="application/octet-stream", category=DocumentCategory.autre)

def test_refresh_expiry(db, company, storage):
    svc = DocumentService(db, storage)
    d = svc.upload(filename="att.pdf", data=b"%PDF", content_type="application/pdf", category=DocumentCategory.attestation,
                   expires_at=date.today() - timedelta(days=1))
    assert refresh_expiry_statuses(db) == 1 and d.status == DocumentStatus.expired
```

```python
# tests/api/test_documents.py
def test_upload_list_download(auth_client, company, storage):
    files = {"file": ("kbis.pdf", b"%PDF-1.4 test", "application/pdf")}
    r = auth_client.post("/api/v1/documents", files=files, data={"category": "administratif", "tags": "kbis,2026"})
    assert r.status_code == 201; did = r.json()["id"]
    assert auth_client.get("/api/v1/documents?category=administratif").json()["total"] == 1
    d = auth_client.get(f"/api/v1/documents/{did}/download")
    assert d.status_code == 200 and d.content == b"%PDF-1.4 test"
```

- [ ] **Step 2 : Run** → FAIL. **Step 3 : Implémentation** (service — les endpoints mappent 1:1)

```python
# app/services/documents.py
import hashlib
from datetime import date
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.connectors.storage.base import StorageProvider, build_key
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.models.document import (CompanyDocument, DocumentCategory, DocumentKind, DocumentStatus, DocumentVersion,
                                 ExtractionStatus)
from app.services.company import CompanyService

ALLOWED_MIMES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt", "application/zip": ".zip", "application/x-zip-compressed": ".zip",
}

def validate_upload(filename: str, data: bytes, content_type: str) -> str:
    if content_type not in ALLOWED_MIMES or not filename.lower().endswith(ALLOWED_MIMES[content_type]):
        raise ValueError("Type de fichier non autorisé (PDF, DOCX, XLSX, TXT, ZIP)")
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux (max {get_settings().max_upload_mb} Mo)")
    return hashlib.sha256(data).hexdigest()

class DocumentService:
    def __init__(self, db: Session, storage: StorageProvider, user_id=None):
        self.db, self.storage, self.user_id = db, storage, user_id

    def upload(self, *, filename, data, content_type, category: DocumentCategory, **meta) -> CompanyDocument:
        sha = validate_upload(filename, data, content_type)
        company = CompanyService.get_or_create(self.db)
        dup = self.db.scalar(select(CompanyDocument).where(CompanyDocument.sha256 == sha, CompanyDocument.category == category,
                                                           CompanyDocument.status != DocumentStatus.archived))
        if dup: raise ConflictError(f"Document identique déjà présent : {dup.name}")
        key = build_key("company", sha, filename)
        self.storage.put(key, data, content_type)
        doc = CompanyDocument(company_id=company.id, name=meta.pop("name", None) or filename, category=category, storage_key=key,
                              mime_type=content_type, size_bytes=len(data), sha256=sha, **meta)
        self.db.add(doc); self.db.flush()
        self.db.add(DocumentVersion(document_kind=DocumentKind.company, document_id=doc.id, version_number=1, storage_key=key, sha256=sha))
        record_audit(self.db, action="document.uploaded", entity_kind="company_document", entity_id=doc.id,
                     payload={"name": doc.name, "category": category}, user_id=self.user_id)
        return doc

    def new_version(self, doc: CompanyDocument, *, filename, data, content_type, changelog=None) -> CompanyDocument:
        sha = validate_upload(filename, data, content_type)
        key = build_key("company", sha, filename); self.storage.put(key, data, content_type)
        doc.version += 1; doc.storage_key = key; doc.sha256 = sha; doc.size_bytes = len(data); doc.mime_type = content_type
        doc.extraction_status = ExtractionStatus.pending
        self.db.add(DocumentVersion(document_kind=DocumentKind.company, document_id=doc.id, version_number=doc.version,
                                    storage_key=key, sha256=sha, changelog=changelog))
        record_audit(self.db, action="document.versioned", entity_kind="company_document", entity_id=doc.id,
                     payload={"version": doc.version}, user_id=self.user_id)
        return doc

    def versions(self, doc) -> list[DocumentVersion]:
        return list(self.db.scalars(select(DocumentVersion).where(DocumentVersion.document_kind == DocumentKind.company,
                                                                  DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number)))

    def archive(self, doc) -> None:
        doc.status = DocumentStatus.archived
        record_audit(self.db, action="document.archived", entity_kind="company_document", entity_id=doc.id, user_id=self.user_id)

def refresh_expiry_statuses(db: Session) -> int:
    res = db.execute(update(CompanyDocument).where(CompanyDocument.status == DocumentStatus.valid,
                                                   CompanyDocument.expires_at < date.today()).values(status=DocumentStatus.expired))
    return res.rowcount
```

Endpoints `app/api/v1/documents.py` : `POST /documents` (multipart `file` + `Form` : `category`, `name?`, `description?`, `issued_at?`, `expires_at?`, `tags?` CSV) → 201 ; `GET /documents?category=&status=&tag=&q=&usable_only=` paginé ; `GET /documents/{id}` ; `PATCH /documents/{id}` (métadonnées) ; `POST /documents/{id}/versions` (multipart + `changelog`) ; `GET /documents/{id}/versions` ; `GET /documents/{id}/download` → `Response(content=storage.get(key), media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})` ; `DELETE /documents/{id}` → archive (204). `ValueError` → 422 via un handler dans `errors.py`. `DocumentOut` inclut `is_expired`, `is_usable`.

```python
# app/workers/tasks/scheduled.py
from app.core.db import SessionLocal
from app.services.documents import refresh_expiry_statuses
from app.workers.celery_app import celery_app

@celery_app.task(name="tender_ai.scheduled.refresh_document_expiry")
def refresh_document_expiry() -> int:
    with SessionLocal() as db:
        n = refresh_expiry_statuses(db); db.commit(); return n
```
Beat (dans `celery_app.py`, `from celery.schedules import crontab`) : `celery_app.conf.beat_schedule["refresh-document-expiry"] = {"task": "tender_ai.scheduled.refresh_document_expiry", "schedule": crontab(hour=1, minute=0)}`.

- [ ] **Step 4 : Run** → PASS. **Step 5 : Commit** `feat(documents): upload, versions, download, expiry rule RB-007`.

---

### Task 2.4 : Frontend — page Profil entreprise

**Files:**
- Create: `frontend/src/app/(app)/company/page.tsx`, `frontend/src/lib/queries/company.ts`, `frontend/src/components/company/ProfileForm.tsx`, `SkillsTab.tsx`, `TechnologiesTab.tsx`, `CertificationsTab.tsx`, `ExpertsTab.tsx`, `ProjectsTab.tsx`, `ReferencesTab.tsx`, `frontend/src/components/common/EntityTable.tsx`, `EntityDialog.tsx`
- Test: `frontend/tests/EntityTable.test.tsx`

**Interfaces:**
- Produces: `EntityTable<T>({columns, rows, onEdit, onDelete})`, `EntityDialog({schema, fields, defaultValues, onSubmit})` génériques réutilisés par toutes les sous-ressources ; hooks `useCompanyProfile()`, `useUpdateProfile()`, `useEntityList(name)`, `useCreateEntity(name)`, `useUpdateEntity(name)`, `useDeleteEntity(name)` (TanStack Query, invalidation par clé `["company", name]`).

- [ ] **Step 1 : Test `EntityTable.test.tsx`** : rend 2 lignes, clic « Supprimer » appelle `onDelete(row)` ; état vide affiche « Aucun élément ».
- [ ] **Step 2 : Run** → FAIL. **Step 3 : Implémenter** `EntityTable`, `EntityDialog` (react-hook-form + zod, champs texte/date/select/tags), la page avec `<Tabs>` : Informations (ProfileForm : raison sociale, nom commercial, description, pays, ville, adresse, site, email, téléphone, secteurs (tags), positionnement), puis un onglet par sous-ressource avec bouton « Ajouter », tableau, édition, suppression avec confirmation. Certifications : badge rouge « Expirée » si `!is_valid`.
- [ ] **Step 4 : Run** `npm test` → PASS ; vérification manuelle : créer le profil InnoSustain complet.
- [ ] **Step 5 : Commit** `feat(frontend): company profile page with sub-resource tabs`.

---

### Task 2.5 : Frontend — page Documents entreprise

**Files:**
- Create: `frontend/src/app/(app)/documents/page.tsx`, `frontend/src/lib/queries/documents.ts`, `frontend/src/components/documents/UploadDialog.tsx`, `DocumentsTable.tsx`, `DocumentDrawer.tsx`
- Test: `frontend/tests/DocumentsTable.test.tsx`

**Interfaces:**
- Produces: `useDocuments(filters)`, `useUploadDocument()` (FormData), `useNewVersion(id)`, `useArchiveDocument()` ; `DocumentsTable` avec badges de statut (`valid` vert, `expired` rouge, `archived` gris) et colonne expiration.

- [ ] **Step 1 : Test** : `DocumentsTable` affiche badge « Expiré » pour une ligne `is_expired: true`. **Step 2 :** FAIL. **Step 3 :** Implémenter : filtres (catégorie, statut, recherche), upload (drag & drop + métadonnées), drawer de détail (versions, téléchargement, nouvelle version, archiver). **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): company documents page`.

**Fin de Phase 2 — critères :** profil InnoSustain saisi de bout en bout ; un document expiré est marqué et exclu de `usable_only=true` ; tests verts.

---

# PHASE 3 — Recherche & collecte (S4)

### Task 3.1 : Modèles recherche/sources/tenders + migration

**Files:**
- Create: `backend/app/models/tender.py`, `backend/alembic/versions/0005_tenders.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_tender_models.py`

**Interfaces:**
- Produces: `SearchProfile`, `TenderSource` (+ `SourceKind`), `Tender` (+ `TenderStatus`, `Urgency`), `TenderSourceLink`, `TenderDocument` (+ `DownloadStatus`) — colonnes de la section 2 (la colonne `embedding` est ajoutée en 4.1).
- `TenderStatus` : `NOUVEAU, A_ANALYSER, GO, NO_GO, PREPARATION, VALIDATION, PRET, SOUMIS, GAGNE, PERDU, ARCHIVE`. `Urgency` : `none, low, medium, high, critical`. `Tender.days_left -> int | None`.

- [ ] **Step 1 : Test** : créer un `Tender` avec `deadline_at = now + 5 j` → `days_left == 5` ; statut par défaut `NOUVEAU` ; `TenderSourceLink.url` unique (IntegrityError sur doublon).
- [ ] **Step 2 :** FAIL. **Step 3 :** modèles (extrait des points non triviaux)

```python
class TenderStatus(str, enum.Enum):
    NOUVEAU="NOUVEAU"; A_ANALYSER="A_ANALYSER"; GO="GO"; NO_GO="NO_GO"; PREPARATION="PREPARATION"; VALIDATION="VALIDATION"
    PRET="PRET"; SOUMIS="SOUMIS"; GAGNE="GAGNE"; PERDU="PERDU"; ARCHIVE="ARCHIVE"
class Urgency(str, enum.Enum): none="none"; low="low"; medium="medium"; high="high"; critical="critical"
class SourceKind(str, enum.Enum): search_engine="search_engine"; rss="rss"; portal="portal"; website="website"; api="api"

class Tender(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenders"
    # … colonnes section 2 …
    status: Mapped[TenderStatus] = mapped_column(String(16), default=TenderStatus.NOUVEAU, index=True)
    urgency: Mapped[Urgency] = mapped_column(String(16), default=Urgency.none)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(40), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON); extra: Mapped[dict] = mapped_column(JSON, default=dict)
    source_links: Mapped[list["TenderSourceLink"]] = relationship(cascade="all, delete-orphan")
    documents: Mapped[list["TenderDocument"]] = relationship(cascade="all, delete-orphan")
    @property
    def days_left(self) -> int | None:
        return None if self.deadline_at is None else (self.deadline_at.date() - date.today()).days
```
`TenderSource.config` (JSON) attendu par type : `search_engine` → `{"include_domains": [...], "max_results": 10}` ; `rss` → `{}` ; `portal`/`website` → `{"listing_paths": ["/appels-offres"], "link_pattern": "regex", "render_js": false, "max_links": 30}`.

- [ ] **Step 4 :** migration `0005_tenders`, PASS. **Step 5 : Commit** `feat(tenders): search profiles, sources, tenders, links, documents models`.

---

### Task 3.2 : Interfaces connecteurs + fakes + schéma `TenderCandidate`

**Files:**
- Create: `backend/app/connectors/search/base.py`, `search/fake.py`, `backend/app/connectors/crawl/base.py`, `crawl/fake.py`, `backend/app/ai/llm.py` (Protocol + `FakeLLM`), `backend/app/ai/outputs.py` (`TenderCandidate`), `backend/app/connectors/extractor.py` (`TenderExtractor` Protocol + `FakeTenderExtractor`)
- Modify: `backend/tests/conftest.py` (fixtures `fake_search`, `fake_crawler`, `fake_llm`, overrides `get_web_search`, `get_crawler`, `get_llm` dans `deps.py`)
- Test: `backend/tests/unit/test_fakes.py`

**Interfaces:**
- Produces: les Protocols de la section 3 ; `FakeWebSearch(results: dict[str, list[SearchResult]])` (clé = sous-chaîne de la requête, `"*"` = défaut) ; `FakeCrawler(pages: dict[str, CrawlResult])` (URL inconnue → `status_code=404`, `text=""`) ; `FakeLLM(structured_responses: list[BaseModel] | Callable[[str, type], BaseModel], text_responses: list[str])` qui journalise chaque appel dans `.calls` (`[{"system", "user", "output", "tier"}]`) ; `TenderExtractor.extract(page: CrawlResult) -> TenderCandidate | None` ; `FakeTenderExtractor(mapping: dict[url, TenderCandidate])`.
- Helper de test `tests/factories.py::page(url: str, *, text: str = "", html: str | None = None, links: list[str] | None = None, status_code: int = 200) -> CrawlResult`.
- Dépendances `app/core/deps.py` : `get_web_search()`, `get_crawler()`, `get_llm()`, `get_embeddings()`, `get_tender_extractor()` (fonctions `lru_cache`, choisies par settings). Comme les workers les appellent directement (pas via FastAPI), les fixtures `fake_search`, `fake_crawler`, `fake_llm`, `fake_extractor` font `monkeypatch.setattr(app.core.deps, "get_web_search", lambda: fake_search)` etc. — et non `dependency_overrides`.

```python
# app/ai/outputs.py
from datetime import date
from pydantic import BaseModel, Field

class TenderCandidate(BaseModel):
    is_tender: bool = Field(description="La page décrit-elle un appel d'offres / consultation ?")
    confidence: float = Field(ge=0, le=1)
    title: str = ""
    organization: str | None = None
    organization_type: str | None = None
    reference: str | None = None
    country: str | None = None
    region: str | None = None
    sector: str | None = None
    market_type: str | None = None
    description: str = ""
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str | None = None
    published_at: date | None = None
    deadline_at: date | None = None
    questions_deadline_at: date | None = None
    source_url: str = ""
    document_urls: list[str] = []
    technologies: list[str] = []
    required_certifications: list[str] = []
```

- [ ] **Step 1 : Test** : `FakeLLM([TenderCandidate(is_tender=True, confidence=0.9, title="X")]).structured(system="s", user="u", output=TenderCandidate).title == "X"` et `.calls[0]["output"] is TenderCandidate` ; `FakeCrawler({}).fetch("http://x").status_code == 404`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter les fakes et les dépendances `get_web_search()`, `get_crawler()`, `get_llm()` dans `deps.py` (choisies par settings ; en `APP_ENV=test` retournent les fakes vides par défaut). **Step 4 :** PASS. **Step 5 : Commit** `feat(connectors): provider protocols, fakes, TenderCandidate schema`.

---

### Task 3.3 : Implémentations réelles — Tavily, crawler httpx, crawler Playwright, RSS

**Files:**
- Create: `backend/app/connectors/search/tavily.py`, `backend/app/connectors/crawl/httpx_crawler.py`, `crawl/playwright_crawler.py`, `backend/app/connectors/rss.py`, `backend/app/connectors/html.py` (`html_to_text`, `extract_links`)
- Test: `backend/tests/unit/test_html.py`, `backend/tests/unit/test_httpx_crawler.py` (avec `httpx.MockTransport`), `backend/tests/unit/test_rss.py` (flux RSS fixture)

**Interfaces:**
- Produces: `TavilySearch(api_key)`, `HttpxCrawler(timeout=30, max_bytes=5_000_000, user_agent="tender-ai/1.0", respect_robots=True)` (retry 3× backoff via tenacity sur erreurs réseau/5xx, jamais sur 4xx ; consulte `robots.txt` via `urllib.robotparser` et renvoie `status_code=451, text=""` si l'URL est interdite — CdC §37), `PlaywrightCrawler()` (chromium headless, `wait_until="networkidle"`, même règle robots), `RssConnector.fetch(feed_url) -> list[SearchResult]`, `html_to_text(html) -> str` (supprime script/style/nav/footer, conserve les sauts de ligne), `extract_links(html, base_url) -> list[str]` (absolues, dédupliquées, même domaine en premier).

- [ ] **Step 1 : Tests**

```python
def test_html_to_text_strips_noise():
    html = "<html><head><style>x</style></head><body><nav>menu</nav><h1>Appel d'offres</h1><p>Objet : refonte SI</p><script>1</script></body></html>"
    assert html_to_text(html) == "Appel d'offres\nObjet : refonte SI"

def test_httpx_crawler_retries_then_succeeds():
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 2 else httpx.Response(200, text="<p>ok</p>")
    crawler = HttpxCrawler(transport=httpx.MockTransport(handler))
    assert crawler.fetch("https://example.org/ao").text == "ok" and calls["n"] == 2

def test_rss_parses_items(fixtures_dir):
    items = RssConnector.parse((fixtures_dir / "feed.xml").read_text())
    assert items[0].url.startswith("http") and items[0].source_name == "rss"
```

- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter (Tavily : `client.search(query, max_results=..., include_domains=...)` → `SearchResult(source_name="tavily")` ; Playwright : `sync_playwright()` ; `playwright install chromium` ajouté au Dockerfile backend : `RUN uv run playwright install --with-deps chromium`). **Step 4 :** PASS. **Step 5 : Commit** `feat(connectors): tavily, httpx/playwright crawlers, rss`.

---

### Task 3.4 : LLM OpenAI + extracteur d'appel d'offres (prompt versionné)

**Files:**
- Create: `backend/app/ai/openai_llm.py`, `backend/app/ai/prompts/__init__.py`, `backend/app/ai/prompts/tender_extract.py`, `backend/app/connectors/llm_extractor.py`
- Test: `backend/tests/unit/test_tender_extractor.py`

**Interfaces:**
- Produces: `OpenAILLM(settings)` implémentant `LLMProvider` (utilise `client.beta.chat.completions.parse(model=…, messages=…, response_format=output, temperature=…)` ; retry 3× sur `RateLimitError`/`APIConnectionError` ; journalise modèle, tokens, durée) ; `LLMTenderExtractor(llm, min_confidence=0.6).extract(page) -> TenderCandidate | None` ; `tender_extract.PROMPT_VERSION = "v1"`, `SYSTEM`, `user_prompt(page: CrawlResult, max_chars=12000) -> str`.

- [ ] **Step 1 : Test**

```python
def test_extractor_returns_none_when_not_tender():
    llm = FakeLLM([TenderCandidate(is_tender=False, confidence=0.9)])
    assert LLMTenderExtractor(llm).extract(page("https://x/blog")) is None

def test_extractor_fills_source_url_and_truncates():
    llm = FakeLLM([TenderCandidate(is_tender=True, confidence=0.8, title="AO SI")])
    cand = LLMTenderExtractor(llm).extract(page("https://x/ao", text="a" * 50_000))
    assert cand.source_url == "https://x/ao" and len(llm.calls[0]["user"]) < 13_000
```

- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. Le prompt système impose : répondre uniquement selon le schéma, `is_tender=false` pour actualités/résultats d'attribution/pages génériques, dates au format ISO, ne rien inventer (`null` si absent), `document_urls` = liens vers DCE/PDF/ZIP visibles dans la page (les liens sont passés au prompt).
- [ ] **Step 4 :** PASS. **Step 5 : Commit** `feat(ai): OpenAI provider and tender extractor prompt v1`.

---

### Task 3.5 : Job `search_tenders` (orchestration multi-sources résiliente)

**Files:**
- Create: `backend/app/services/query_builder.py`, `backend/app/services/collect.py`, `backend/app/services/ingest.py` (v1 : insertion simple, remplacée en Phase 4), `backend/app/workers/tasks/search.py`
- Modify: `backend/app/workers/celery_app.py` (include), `backend/tests/conftest.py` (fixtures `search_profile` — profil « IT Maroc » avec keywords `["SI", "ERP"]`, sectors `["IT"]`, countries `["MA"]` — et `two_sources` — `[TenderSource(kind="search_engine", config={"include_domains": []}), TenderSource(kind="rss", base_url="https://feed/rss")]`)
- Test: `backend/tests/unit/test_query_builder.py`, `backend/tests/workers/test_search_tenders.py`

**Interfaces:**
- Produces: `build_queries(profile: SearchProfile, max_queries=8) -> list[str]` (produit cartésien limité : mots-clés × secteurs × pays, + « appel d'offres » / « consultation », déduplique, tronque) ; `CollectService(search, crawler, extractor).collect_source(source, queries, *, log) -> list[TenderCandidate]` (par type de source, capture toute exception et la renvoie dans `SourceReport(source_id, status, error, found, candidates)`) ; `IngestService(db).ingest(candidates, profile) -> IngestStats(created, merged, skipped, invalid)` ; tâche `search_tenders(db, job, *, search_profile_id: str) -> dict` (met `job.progress` par source, `source.last_run_at/last_status/last_error`, `profile.last_run_at`, audit `search.launched`).

- [ ] **Step 1 : Tests**

```python
def test_build_queries_limits_and_dedupes(db):
    p = SearchProfile(name="p", keywords=["ERP", "data"], sectors=["santé"], countries=["MA", "FR"])
    q = build_queries(p, max_queries=4)
    assert len(q) == 4 and len(set(q)) == 4 and all("appel d'offres" in s for s in q)

def test_search_job_survives_source_failure(db, run_jobs_inline, search_profile, two_sources, fake_search, fake_crawler, fake_extractor):
    fake_search.results["*"] = [SearchResult(url="https://ok/ao1", title="AO 1", source_name="tavily")]
    fake_crawler.pages["https://ok/ao1"] = page("https://ok/ao1", text="Appel d'offres 1")
    fake_extractor.mapping["https://ok/ao1"] = TenderCandidate(is_tender=True, confidence=.9, title="AO 1", source_url="https://ok/ao1")
    two_sources[1].base_url = "https://broken/feed"      # RSS inaccessible
    job = JobService.enqueue(db, "search_tenders", entity_kind="search_profile", entity_id=search_profile.id, search_profile_id=str(search_profile.id))
    db.refresh(job)
    assert job.status == JobStatus.done and job.result["created"] == 1
    assert job.result["sources"][str(two_sources[1].id)]["status"] == "error"
    assert db.scalar(select(func.count(Tender.id))) == 1
```

- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter (`collect_source` : `search_engine` → `search.search(q, include_domains=config)` pour chaque requête ; `rss` → `RssConnector.fetch(base_url)` ; `portal`/`website` → `crawler.fetch(base_url + listing_path)` puis `extract_links` filtrés par `link_pattern` ; `api` → `SourceReport(status="skipped", error="adapter non implémenté")` ; chaque URL candidate → `crawler.fetch` → `extractor.extract` ; URL déjà présente dans `tender_source_links` → ignorée avant tout appel réseau (idempotence)). Les providers sont obtenus via `deps.get_web_search()/get_crawler()/get_llm()` pour que les tests surchargent.
- [ ] **Step 4 :** PASS. **Step 5 : Commit** `feat(search): resilient multi-source search_tenders job`.

---

### Task 3.6 : Endpoints profils de recherche, sources, recherches, tenders

**Files:**
- Create: `backend/app/schemas/tender.py`, `backend/app/api/v1/search_profiles.py`, `sources.py`, `searches.py`, `tenders.py`, `backend/app/repositories/tenders.py`
- Modify: `backend/app/api/router.py`, `backend/app/api/crud_router.py` (paramètre `scoped_to_company: bool = True` — `False` pour profils et sources qui n'ont pas de `company_id`)
- Test: `backend/tests/api/test_search_profiles.py`, `test_sources.py`, `test_searches.py`, `test_tenders.py`

**Interfaces:**
- Produces: `TenderListParams(status, sector, country, q, deadline_before, active_only=True, sort in {created,-created,deadline,-score}, page, size)` ; `tenders_repo.search(db, params) -> (items, total)` ; `TenderOut` (inclut `days_left`, `urgency`, `source_count`, `score_total: float | None` — jointure `tender_scores` ajoutée en Phase 5, `None` avant) ; `POST /searches {search_profile_id}` → 202 `JobOut` ; `POST /sources/{id}/test` → lance `collect_source` synchrone limité à 3 URLs et renvoie `SourceReport` (permet de vérifier une configuration).

- [ ] **Step 1 : Tests** (extraits) : création profil ; création source `rss` ; `POST /searches` renvoie 202 + `job.type == "search_tenders"` et, avec `run_jobs_inline`, crée les tenders ; `GET /tenders?q=SI` filtre sur titre/description (`ILIKE`) ; `GET /tenders/{id}` 404 sur UUID inconnu ; `active_only` par défaut exclut `is_active=false`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(api): search profiles, sources, searches, tenders endpoints`.

---

### Task 3.7 : Frontend — Paramètres de recherche, Sources, Opportunités (liste), suivi de job

**Files:**
- Create: `frontend/src/app/(app)/search-profiles/page.tsx`, `sources/page.tsx`, `tenders/page.tsx`, `frontend/src/lib/queries/{searchProfiles,sources,tenders,jobs}.ts`, `frontend/src/components/jobs/JobProgress.tsx`, `frontend/src/components/tenders/TendersTable.tsx`, `TenderFilters.tsx`
- Test: `frontend/tests/JobProgress.test.tsx`

**Interfaces:**
- Produces: `useJob(id, {poll: true})` (refetch toutes les 2 s tant que `pending|running`) ; `JobProgress({jobId})` (barre + message + erreur) ; bouton « Lancer la recherche » sur un profil → `POST /searches` → toast + `JobProgress` ; `TendersTable` (titre, organisme, pays, secteur, échéance + badge urgence, statut, sources, score « — ») avec tri et filtres.

- [ ] **Step 1 : Test** : `JobProgress` affiche « Terminé » quand `status: "done"` et le message d'erreur quand `failed`. **Step 2 :** FAIL. **Step 3 :** implémenter les trois pages (formulaires profils avec champs multi-tags, table des sources avec toggle actif + bouton « Tester », liste des opportunités). **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): search profiles, sources, tenders list, job progress`.

**Fin de Phase 3 — critères :** avec une vraie clé Tavily et un flux RSS réel, « Lancer la recherche » crée des fiches `tenders` visibles dans la liste ; une source cassée est signalée sans faire échouer le job.

---

# PHASE 4 — Normalisation & déduplication (S5)

### Task 4.1 : Normaliseur + empreinte + colonne `embedding`

**Files:**
- Create: `backend/app/services/normalize.py`, `backend/app/ai/embeddings.py` (Protocol + `OpenAIEmbeddings` + `FakeEmbeddings`), `backend/alembic/versions/0006_tender_embedding.py`
- Modify: `backend/app/models/tender.py` (`embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))`), `backend/app/core/deps.py` (`get_embeddings()`)
- Test: `backend/tests/unit/test_normalize.py`, `backend/tests/unit/test_embeddings_fake.py`

**Interfaces:**
- Produces: `NormalizedTender` (mêmes champs que `TenderCandidate` + `fingerprint: str`, `norm_title: str`, `norm_org: str`, `norm_reference: str | None`) ; `normalize(c: TenderCandidate) -> NormalizedTender` ; `FakeEmbeddings(dimensions=1536)` déterministe (hash du texte → vecteur) ; `EmbeddingProvider.embed(texts) -> list[list[float]]`.
- Règles : espaces compressés ; `norm_title` = minuscules sans accents ni ponctuation ; `norm_org` idem ; `norm_reference` = majuscules sans espaces/tirets ; pays → ISO-2 via `pycountry` (+ table courte FR/MA/… « Maroc » → « MA ») ; devise majuscule ; `fingerprint = sha1(f"{norm_org}|{norm_title[:80]}|{deadline_at or ''}")[:40]`.

- [ ] **Step 1 : Tests**

```python
def test_normalize_country_and_reference():
    n = normalize(TenderCandidate(is_tender=True, confidence=1, title="  Refonte   du SI ", organization="Ministère X", country="Maroc", reference="ao 12-2026/A"))
    assert n.country == "MA" and n.norm_reference == "AO122026/A" and n.title == "Refonte du SI"

def test_fingerprint_stable_across_case_and_accents():
    a = normalize(TenderCandidate(is_tender=True, confidence=1, title="Réfonte du SI", organization="Ministère X", deadline_at=date(2026,10,1)))
    b = normalize(TenderCandidate(is_tender=True, confidence=1, title="REFONTE DU SI", organization="ministere x", deadline_at=date(2026,10,1)))
    assert a.fingerprint == b.fingerprint
```

- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter (`unicodedata.normalize("NFKD")` pour les accents). Migration ajoute `embedding` (import `from pgvector.sqlalchemy import Vector` dans `env.py`). **Step 4 :** PASS. **Step 5 : Commit** `feat(normalize): candidate normalization, fingerprint, embeddings provider`.

---

### Task 4.2 : Déduplicateur (RB-001) et fusion

**Files:**
- Create: `backend/app/services/dedup.py`
- Test: `backend/tests/unit/test_dedup.py`

**Interfaces:**
- Produces: `Deduplicator(db, embeddings, *, fuzzy_threshold=90, semantic_threshold=0.92).find_duplicate(n: NormalizedTender) -> Tender | None` ; `merge_into(tender: Tender, n: NormalizedTender, source, raw) -> Tender` (ajoute un `TenderSourceLink`, remplit les champs `None` du tender existant — jamais d'écrasement —, étend `extra["document_urls"]`, audit `tender.merged`).
- Ordre des règles : (1) URL déjà liée ; (2) `norm_reference` + `norm_org` identiques ; (3) `fingerprint` identique ; (4) même `norm_org` ou même `deadline_at` **et** `rapidfuzz.fuzz.token_set_ratio(norm_title, t.norm_title) >= 90` ; (5) `embedding` cosinus ≥ 0.92 parmi les tenders actifs dont la deadline est à ± 3 jours (ou nulle). Chaque règle retenue est journalisée (`rule`).

- [ ] **Step 1 : Tests** : un cas par règle (1→5) + un cas « pas doublon » (titres différents, même organisme) ; `merge_into` conserve `budget_max` existant et remplit `reference` manquante.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter (règle 5 : `select(Tender).where(Tender.is_active, Tender.embedding.isnot(None), …).order_by(Tender.embedding.cosine_distance(vec)).limit(3)` puis filtrer `1 - distance >= threshold`). **Step 4 :** PASS. **Step 5 : Commit** `feat(dedup): rule-based + fuzzy + semantic duplicate detection and merge`.

---

### Task 4.3 : Pipeline d'ingestion complet + endpoint sources d'un tender

**Files:**
- Modify: `backend/app/services/ingest.py` (v2), `backend/app/api/v1/tenders.py` (`GET /tenders/{id}/sources`)
- Test: `backend/tests/unit/test_ingest.py`, `backend/tests/api/test_tender_sources.py`

**Interfaces:**
- Produces: `IngestService(db, embeddings, dedup).ingest(candidates, profile, source) -> IngestStats(created, merged, skipped, invalid, details: list[{url, action, rule}])`. Pipeline par candidat : `normalize` → validation (`is_tender`, `title` non vide, `confidence ≥ 0.6`, sinon `invalid`) → `find_duplicate` → `merge_into` ou création (`Tender` + `TenderSourceLink` + `embedding` du `title + description[:500]` + audit `tender.created`) → `is_active = deadline_at is None or deadline_at >= today` (RB-002 dès l'ingestion).

- [ ] **Step 1 : Test** : deux candidats équivalents (même AO sur deux URLs) ⇒ `created == 1, merged == 1` et `GET /tenders/{id}/sources` renvoie 2 liens ; candidat avec deadline passée ⇒ créé mais `is_active == False`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(ingest): normalize → validate → dedup → persist pipeline`.

---

### Task 4.4 : Règle RB-002 (expiration planifiée) et urgence

**Files:**
- Create: `backend/app/services/deadlines.py`
- Modify: `backend/app/workers/tasks/scheduled.py`, `backend/app/workers/celery_app.py` (beat)
- Test: `backend/tests/unit/test_deadlines.py`

**Interfaces:**
- Produces: `compute_urgency(days_left: int | None) -> Urgency` (`None`→none ; `>14`→low ; `8–14`→medium ; `3–7`→high ; `≤2`→critical) ; `refresh_tender_deadlines(db) -> dict(expired: int, updated: int)` (désactive les tenders dont `deadline_at < now()` et recalcule `urgency` de tous les actifs) ; tâche beat `refresh_tender_deadlines` quotidienne 02:00 UTC.

- [ ] **Step 1 : Tests** (avec `freezegun`) : tender à J-1 devient inactif ; tender à J+2 → `critical`. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(tenders): RB-002 expiry and urgency refresh`.

---

### Task 4.5 : Frontend — sources regroupées et indicateurs de doublons

**Files:**
- Modify: `frontend/src/components/tenders/TendersTable.tsx` (colonne « Sources » = nombre de liens avec tooltip des URLs), `frontend/src/app/(app)/tenders/page.tsx` (toggle « Inclure les expirées »), `frontend/src/lib/queries/tenders.ts` (`useTenderSources(id)`)
- Test: `frontend/tests/TendersTable.test.tsx`

- [ ] **Step 1 : Test** : la ligne affiche « 2 sources » quand `source_count: 2`. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): merged sources indicator, expired toggle`.

**Fin de Phase 4 — critères :** deux annonces du même AO ⇒ une seule fiche avec 2 sources (critère d'acceptation CdC §35) ; un AO expiré disparaît de la liste par défaut.

---
# PHASE 5 — Matching, scoring, GO/NO-GO (S6)

### Task 5.1 : Modèles score / décision / historique + migration

**Files:**
- Create: `backend/app/models/scoring.py`, `backend/alembic/versions/0007_scoring.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/tender.py` (relations `score`, `decisions`, `status_history`)

**Interfaces:**
- Produces: `TenderScore` (colonnes section 2, `tender_id` unique), `TenderDecision`, `TenderStatusHistory`.

- [ ] **Step 1 :** modèles + migration ; test minimal `test_score_unique_per_tender` (2e insert ⇒ `IntegrityError`). **Step 2 :** PASS. **Step 3 : Commit** `feat(scoring): score, decision, status history models`.

---

### Task 5.2 : Moteur de scoring déterministe explicable

**Files:**
- Create: `backend/app/services/scoring.py`
- Test: `backend/tests/unit/test_scoring.py`

**Interfaces:**
- Produces:

```python
WEIGHTS = {"sector": 20, "technologies": 15, "skills": 15, "country": 10, "budget": 10, "experience": 15, "certifications": 5, "eligibility": 10}
SCORING_VERSION = "1.0"

class SubScore(BaseModel):
    key: str; score: float; weight: int; reason: str; matched: list[str] = []; missing: list[str] = []

class ScoreResult(BaseModel):
    total: float; breakdown: list[SubScore]; strengths: list[str]; weaknesses: list[str]

def compute_score(tender: Tender, company: Company, profile: SearchProfile | None, eligibility_ratio: float | None) -> ScoreResult
```
- Règles (chaque sous-score ∈ [0, 100] avec `reason` en français) :
  - `sector` : 100 si `tender.sector` ≈ un secteur entreprise (`token_set_ratio ≥ 85`), 50 si un mot-clé du profil de recherche apparaît dans titre/description, sinon 0.
  - `technologies` : `tender.extra["technologies"]` ∩ technologies entreprise (fuzzy ≥ 85) / total demandé ; liste vide demandée ⇒ 60 « non précisé ».
  - `skills` : mots des `skills` de l'entreprise trouvés dans titre+description ⇒ min(100, 25 × nb) ; 0 sinon.
  - `country` : 100 si `tender.country == company.country` ; 70 si dans `profile.countries` ; 30 si inconnu ; 0 sinon.
  - `budget` : 100 si dans `[profile.budget_min, profile.budget_max]` ; 50 si inconnu ; 20 hors plage.
  - `experience` : projets de même secteur (fuzzy) : 0→0, 1→50, 2→75, ≥3→100 ; cite les titres dans `matched`.
  - `certifications` : requises (`tender.extra["required_certifications"]`) couvertes par des certifications **valides** ; aucune requise ⇒ 100 ; expirée ⇒ dans `missing` avec « (expirée) ».
  - `eligibility` : `eligibility_ratio × 100` si fourni (Phase 7), sinon 50 « non évaluée ».
  - `total = Σ score × weight / 100`, arrondi à 1 décimale. `strengths` = clés avec score ≥ 75 ; `weaknesses` = clés avec score ≤ 40.

- [ ] **Step 1 : Tests** : un cas « parfait » ⇒ `total ≥ 90` ; secteur inconnu ⇒ sous-score 0 avec `reason` ; certification expirée ⇒ `missing` contient « ISO 27001 (expirée) » ; poids somme à 100 (`sum(WEIGHTS.values()) == 100`) ; `breakdown` contient exactement les 8 clés.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(scoring): deterministic explainable score engine v1.0`.

---

### Task 5.3 : Couche IA du score (justification, ajustement borné) + job

**Files:**
- Create: `backend/app/ai/prompts/score_assessment.py`, `backend/app/workers/tasks/scoring.py`, `backend/app/services/score_service.py`
- Modify: `backend/app/ai/outputs.py` (`ScoreAssessment`), `backend/app/workers/celery_app.py`, `backend/app/services/ingest.py` (enfile `calculate_match_score` pour chaque tender créé/fusionné)
- Test: `backend/tests/workers/test_scoring_task.py`

**Interfaces:**
- Produces: `ScoreAssessment(justification: str, strengths: list[str], weaknesses: list[str], adjustment: int = Field(ge=-10, le=10), adjustment_reason: str)` ; `ScoreService(db, llm).score_tender(tender) -> TenderScore` (lit `eligibility_ratio = tender.extra.get("eligibility", {}).get("ratio")` — renseigné en Phase 7, `None` avant —, calcule `compute_score`, appelle le LLM avec profil résumé + fiche AO + breakdown, applique `adjustment` borné, persiste/écrase `TenderScore`, passe le statut `NOUVEAU → A_ANALYSER` si `total ≥ settings.relevance_threshold`, audit `tender.scored`) ; tâche `calculate_match_score(db, job, *, tender_id: str)`.
- RB-004 : `justification` non vide obligatoire — si le LLM échoue, le score est persisté avec `justification = "Justification IA indisponible : " + résumé des sous-scores` et `ai_adjustment = 0`.

- [ ] **Step 1 : Tests** : avec `FakeLLM([ScoreAssessment(justification="ok", strengths=[], weaknesses=[], adjustment=5, adjustment_reason="références")])`, `total == déterministe + 5` ; avec un `FakeLLM` qui lève ⇒ score persisté, `justification` commence par « Justification IA indisponible » ; tender ≥ seuil ⇒ statut `A_ANALYSER`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(scoring): AI justification and bounded adjustment, auto-scoring job`.

---

### Task 5.4 : Machine à états, décision GO/NO-GO, endpoints score/décision/historique/kanban

**Files:**
- Create: `backend/app/services/tender_status.py`, `backend/app/api/v1/scoring.py` (routes `/tenders/{id}/score`, `/decision`, `/status`, `/history`, `/tenders/kanban`)
- Modify: `backend/app/schemas/tender.py` (`TenderScoreOut`, `DecisionIn`, `StatusIn`, `StatusHistoryOut`, `KanbanOut`), `backend/app/api/router.py`, `backend/app/repositories/tenders.py` (jointure score pour `score_total` et tri `-score`)
- Test: `backend/tests/unit/test_tender_status.py`, `backend/tests/api/test_scoring_api.py`

**Interfaces:**
- Produces:

```python
TRANSITIONS: dict[TenderStatus, set[TenderStatus]] = {
    NOUVEAU: {A_ANALYSER, NO_GO, ARCHIVE}, A_ANALYSER: {GO, NO_GO, ARCHIVE}, GO: {PREPARATION, NO_GO},
    NO_GO: {A_ANALYSER, ARCHIVE}, PREPARATION: {VALIDATION, NO_GO}, VALIDATION: {PRET, PREPARATION},
    PRET: {SOUMIS, VALIDATION}, SOUMIS: {GAGNE, PERDU}, GAGNE: {ARCHIVE}, PERDU: {ARCHIVE}, ARCHIVE: set(),
}
def transition(db, tender, to: TenderStatus, *, comment: str | None, user_id) -> Tender   # ForbiddenTransition sinon ; historise + audit tender.status_changed
def decide(db, tender, decision: Literal["go","no_go"], reason: str | None, user_id) -> TenderDecision   # → GO/NO_GO + audit tender.decision
```
- `GET /tenders/kanban` → `{"columns": [{"status": "NOUVEAU", "items": [TenderOut…]}, …]}` (actifs uniquement, sauf GAGNE/PERDU/ARCHIVE affichés 90 jours).

- [ ] **Step 1 : Tests** : `GO → GAGNE` lève `ForbiddenTransition` ; `decide(go)` crée la décision et l'entrée d'historique ; `POST /tenders/{id}/score` relance le job et `GET …/score` renvoie `breakdown` de 8 éléments et `justification` ; `GET /tenders?sort=-score` ordonne.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(tenders): status machine, GO/NO-GO decision, score & kanban endpoints`.

---

### Task 5.5 : Frontend — détail opportunité (score expliqué, GO/NO-GO) et Kanban

**Files:**
- Create: `frontend/src/app/(app)/tenders/[id]/page.tsx` (layout à onglets : Aperçu · Analyse · Exigences · Questions · Candidature · Historique — les 4 derniers onglets sont remplis en phases 6-10), `frontend/src/components/tenders/ScoreCard.tsx`, `ScoreBreakdown.tsx`, `DecisionButtons.tsx`, `StatusTimeline.tsx`, `frontend/src/app/(app)/tenders/kanban/page.tsx`, `frontend/src/components/tenders/KanbanBoard.tsx`
- Test: `frontend/tests/ScoreBreakdown.test.tsx`

**Interfaces:**
- Produces: `ScoreCard` (total /100, badge couleur : ≥70 vert, 40-69 orange, <40 rouge, justification IA avec mention « Assistance IA — à vérifier » (RB-005)), `ScoreBreakdown` (8 lignes : clé, score, poids, raison, matched/missing), `DecisionButtons` (GO / NO-GO avec dialogue de motif), `KanbanBoard` (colonnes du cycle de vie, cartes avec score/échéance/urgence, changement de statut par menu — pas de drag & drop en MVP).

- [ ] **Step 1 : Test** : `ScoreBreakdown` rend 8 lignes et affiche « (expirée) » dans les manquants. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): tender detail with explainable score, decision, kanban`.

**Fin de Phase 5 — critères :** chaque opportunité pertinente a un score + justification (CdC §35) ; GO/NO-GO enregistré et historisé ; tri par score.

---

# PHASE 6 — Pipeline documentaire & analyse IA (S7)

### Task 6.1 : Téléchargement / upload des documents d'un AO

**Files:**
- Create: `backend/app/services/tender_documents.py`, `backend/app/workers/tasks/documents.py`, `backend/app/api/v1/tender_documents.py`
- Modify: `backend/app/workers/celery_app.py`, `backend/app/api/router.py`, `backend/app/schemas/tender.py` (`TenderDocumentOut`)
- Test: `backend/tests/unit/test_tender_documents.py`, `backend/tests/api/test_tender_documents_api.py`

**Interfaces:**
- Produces: `TenderDocumentService(db, storage, crawler_http: httpx.Client)` : `register_urls(tender, urls) -> list[TenderDocument]` (pending, idempotent sur `source_url`), `download(doc) -> TenderDocument` (stream, `max_upload_mb`, MIME par en-tête puis `filetype.guess`, sha256, clé `build_key(f"tenders/{tender_id}", sha, name)`, `download_status done|failed` + `error`), `upload_manual(tender, filename, data, content_type) -> TenderDocument` (réutilise `validate_upload`) ; tâche `download_tender_documents(db, job, *, tender_id)` (un échec de document n'arrête pas les autres ; `progress` par document).
- Endpoints : `GET /tenders/{id}/documents`, `POST /tenders/{id}/documents` (multipart), `POST /tenders/{id}/documents/fetch` (job depuis `extra["document_urls"]`), `GET /tenders/{id}/documents/{docId}/download`.

- [ ] **Step 1 : Tests** : `httpx.MockTransport` renvoyant un PDF pour URL A et 404 pour URL B ⇒ A `done`, B `failed` avec `error`, job `done` avec `result == {"done": 1, "failed": 1}` ; upload manuel refuse `.exe`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(tender-docs): download/upload tender documents with per-document resilience`.

---

### Task 6.2 : Extraction de texte multi-formats (PDF, DOCX, XLSX, TXT, ZIP)

**Files:**
- Create: `backend/app/services/extraction.py`
- Test: `backend/tests/unit/test_extraction.py` (fixtures `sample.pdf` 2 pages, `sample.docx`, `sample.xlsx`, `sample.txt`, `sample.zip` contenant les 4 précédents, `protected.pdf` chiffré)

**Interfaces:**
- Produces:

```python
class ExtractedPage(BaseModel): number: int; text: str
class ExtractedDocument(BaseModel): filename: str; mime_type: str; pages: list[ExtractedPage]; char_count: int
class ExtractionError(Exception): ...
def extract(data: bytes, mime_type: str, filename: str) -> list[ExtractedDocument]    # ZIP ⇒ plusieurs documents, récursion max 1 niveau
```
- PDF : PyMuPDF `page.get_text("text")` ; chiffré/illisible ⇒ `ExtractionError("PDF protégé ou illisible")` ; PDF scanné (0 caractère sur toutes les pages) ⇒ `ExtractionError("PDF sans texte (scan) — OCR non supporté en MVP")`. DOCX : paragraphes + tableaux (cellules jointes par ` | `), une seule « page ». XLSX : une « page » par feuille, lignes jointes par tabulation, max 2 000 lignes/feuille. TXT : décodage utf-8 puis latin-1. ZIP : ignore les entrées > 50 Mo et les types non supportés (listés dans `metadata`), refuse les chemins `../`.

- [ ] **Step 1 : Tests** : PDF ⇒ 2 pages avec le texte attendu ; DOCX ⇒ texte des tableaux présent ; XLSX ⇒ 1 page par feuille ; ZIP ⇒ 4 documents ; `protected.pdf` ⇒ `ExtractionError`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(extraction): multi-format text extraction`.

---

### Task 6.3 : Découpage, embeddings, `document_chunks` (pgvector) + job d'indexation

**Files:**
- Create: `backend/app/models/chunk.py`, `backend/app/services/chunking.py`, `backend/app/services/indexing.py`, `backend/alembic/versions/0008_chunks.py`
- Modify: `backend/app/workers/tasks/documents.py` (tâche `index_document`), `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_chunking.py`, `backend/tests/workers/test_index_document.py`

**Interfaces:**
- Produces: `Chunk(index: int, page: int | None, section: str | None, text: str)` ; `chunk_pages(pages: list[ExtractedPage], *, max_chars=1500, overlap=200) -> list[Chunk]` (coupe aux paragraphes, puis phrases, jamais au milieu d'un mot ; conserve le numéro de page d'origine) ; `DocumentChunk` (section 2, index HNSW `vector_cosine_ops`) ; `IndexingService(db, storage, embeddings).index(kind: Literal["tender_document","company_document"], doc) -> int` (extraction si `extraction_status != done`, stocke `extracted_text` et `page_count`, supprime les anciens chunks de ce document, insère les nouveaux avec embeddings par lots de 64, met `extraction_status`) ; tâche `index_document(db, job, *, kind, document_id)`.
- Un ZIP produit plusieurs `ExtractedDocument` : les chunks portent `metadata["inner_filename"]`.

- [ ] **Step 1 : Tests** : texte de 4 000 caractères en 3 paragraphes ⇒ chunks ≤ 1 500 avec recouvrement ; page conservée ; indexation d'un `sample.pdf` avec `FakeEmbeddings` ⇒ `N` chunks en base et `extraction_status == done` ; PDF protégé ⇒ `extraction_status == failed`, job `done` avec `result["error"]`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(indexing): chunking, embeddings, pgvector chunks, index job`.

---

### Task 6.4 : Analyse IA structurée du dossier + critères d'évaluation

**Files:**
- Create: `backend/app/models/analysis.py` (`TenderAnalysis`, `TenderCriterion`), `backend/app/ai/prompts/tender_analysis.py`, `backend/app/services/analysis.py`, `backend/app/workers/tasks/analysis.py`, `backend/alembic/versions/0009_analysis.py`
- Modify: `backend/app/ai/outputs.py` (`TenderAnalysisOutput`), `backend/app/workers/celery_app.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_analysis_service.py`, `backend/tests/workers/test_analyze_tender.py`

**Interfaces:**
- Produces:

```python
class DatedItem(BaseModel): label: str; date: date | None; source_page: int | None
class CriterionOut(BaseModel): name: str; weight: float | None; description: str | None; source_page: int | None
class RequestedDocument(BaseModel): name: str; mandatory: bool; source_page: int | None
class TenderAnalysisOutput(BaseModel):
    object: str; organization: str | None; reference: str | None; budget: str | None; duration: str | None; location: str | None
    key_dates: list[DatedItem]; deliverables: list[str]; evaluation_criteria: list[CriterionOut]
    requested_documents: list[RequestedDocument]; eligibility_conditions: list[str]; summary: str
```
`AnalysisService(db, llm).analyze(tender) -> TenderAnalysis` : construit le corpus (`extracted_text` de tous les documents `done`, préfixé `=== {filename} — page {n} ===`, tronqué à 120 000 caractères avec priorité aux documents nommés « RC », « CCTP », « CCAP », « règlement », « cahier »), appelle `tier="fast"`, persiste `TenderAnalysis` (upsert) + remplace les `TenderCriterion`, met à jour `tender.summary`, `deadline_at` si absent et trouvé, `extra["requested_documents"]`, audit `tender.analyzed`.
- Tâche `analyze_tender(db, job, *, tender_id)` = chaîne : télécharger les docs manquants → indexer ceux non indexés → analyser → **extraire les exigences (Phase 7, branché en 7.1)**. Le job global expose `progress` 0/25/50/75/100 et `message`.
- Endpoints (dans `api/v1/analysis.py`) : `POST /tenders/{id}/analyze` → 202 job ; `GET /tenders/{id}/analysis` → `TenderAnalysisOut` (+ `criteria`).

- [ ] **Step 1 : Tests** : avec 2 documents indexés et un `FakeLLM` renvoyant un `TenderAnalysisOutput` complet ⇒ `TenderAnalysis` persistée, 3 critères, `tender.summary` renseigné, le prompt contient les marqueurs de page ; tender sans document ⇒ `AppError("Aucun document exploitable")`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(analysis): structured AI analysis of tender documents`.

---

### Task 6.5 : Frontend — page Analyse du dossier

**Files:**
- Create: `frontend/src/components/tenders/DocumentsPanel.tsx`, `AnalysisPanel.tsx`, `frontend/src/lib/queries/analysis.ts`
- Modify: `frontend/src/app/(app)/tenders/[id]/page.tsx` (onglet Analyse)
- Test: `frontend/tests/AnalysisPanel.test.tsx`

**Interfaces:**
- Produces: `DocumentsPanel` (liste des documents : nom, taille, statut téléchargement/extraction avec erreur lisible, upload manuel, bouton « Récupérer les documents ») ; bouton « Analyser le dossier » → `JobProgress` ; `AnalysisPanel` (objet, organisme, budget, durée, lieu, dates clés avec `p. N`, livrables, critères d'évaluation avec poids, documents demandés (obligatoire / facultatif), conditions d'éligibilité, résumé — bandeau « Analyse générée par IA, à vérifier »).

- [ ] **Step 1 : Test** : `AnalysisPanel` affiche « p. 4 » à côté d'une date clé avec `source_page: 4`. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): tender documents and analysis panels`.

**Fin de Phase 6 — critères :** un dossier PDF réel est analysé et ses éléments principaux extraits avec pages sources (CdC §35) ; un document illisible n'empêche pas l'analyse des autres.

---

# PHASE 7 — Exigences, éligibilité, questions (S8)

### Task 7.1 : Extraction structurée des exigences (`TECH-001`, …)

**Files:**
- Create: `backend/app/models/requirement.py`, `backend/app/ai/prompts/requirements_extract.py`, `backend/app/services/requirements.py`, `backend/alembic/versions/0010_requirements.py`
- Modify: `backend/app/ai/outputs.py` (`RequirementOutput`, `RequirementsOutput`), `backend/app/workers/tasks/analysis.py` (étape 4 de la chaîne), `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_requirements_service.py`

**Interfaces:**
- Produces:

```python
class RequirementCategory(str, enum.Enum):
    administrative="administrative"; technique="technique"; financiere="financiere"; juridique="juridique"; experience="experience"
    equipe="equipe"; certification="certification"; methodologie="methodologie"; autre="autre"
CODE_PREFIX = {"administrative":"ADM","technique":"TECH","financiere":"FIN","juridique":"JUR","experience":"EXP","equipe":"EQU","certification":"CERT","methodologie":"METH","autre":"AUT"}
class RequirementStatus(str, enum.Enum): CONFORME="CONFORME"; A_VERIFIER="A_VERIFIER"; NON_CONFORME="NON_CONFORME"; INFO_MANQUANTE="INFO_MANQUANTE"
class Priority(str, enum.Enum): CRITIQUE="CRITIQUE"; IMPORTANTE="IMPORTANTE"; FACULTATIVE="FACULTATIVE"

class RequirementOutput(BaseModel):
    category: RequirementCategory; description: str; is_mandatory: bool; evidence_required: str | None
    priority: Priority; source_document: str | None; source_page: int | None; source_excerpt: str | None
class RequirementsOutput(BaseModel): requirements: list[RequirementOutput]
```
`RequirementsService(db, llm).extract(tender) -> list[TenderRequirement]` : un appel LLM par document (corpus paginé), fusion et déduplication (`token_set_ratio ≥ 92` sur `description`), codes séquentiels par préfixe (`TECH-001`, `TECH-002`, `ADM-001`…), `status = A_VERIFIER` initial, `source_document_id` résolu par nom de fichier ; ré-extraction ⇒ conserve les statuts/justifications déjà saisis manuellement pour les exigences dont la description matche ≥ 95, supprime les autres.
- Endpoints (`api/v1/requirements.py`) : `GET /tenders/{id}/requirements?status=&category=&mandatory=` ; `PATCH /requirements/{id}` (`status`, `justification`, `is_mandatory`, `priority` — audit `requirement.updated`).

- [ ] **Step 1 : Tests** : `FakeLLM` renvoyant 3 exigences dont 2 quasi identiques ⇒ 2 persistées avec codes `TECH-001`, `ADM-001` ; ré-extraction après `PATCH status=CONFORME` conserve le statut.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(requirements): structured requirement extraction with stable codes`.

---

### Task 7.2 : Moteur d'éligibilité (règles + profil) et RB-003

**Files:**
- Create: `backend/app/services/eligibility.py`, `backend/app/workers/tasks/eligibility.py`
- Modify: `backend/app/workers/celery_app.py`, `backend/app/api/v1/requirements.py` (`POST /tenders/{id}/eligibility` → job ; `GET /tenders/{id}/eligibility` → synthèse), `backend/app/services/score_service.py` (utilise `eligibility_ratio`)
- Test: `backend/tests/unit/test_eligibility.py`

**Interfaces:**
- Produces:

```python
class Evidence(BaseModel): kind: Literal["certification","technology","skill","expert","project","document","answer","chunk"]; id: str; label: str
class Judgement(BaseModel): status: RequirementStatus; justification: str; evidence: list[Evidence] = []
class EligibilitySummary(BaseModel):
    total: int; by_status: dict[str, int]; mandatory_unmet: list[str]   # codes
    ratio: float   # (CONFORME + 0.5 × A_VERIFIER) / total ; 1.0 si aucune exigence

class EligibilityEngine:
    def __init__(self, db, company): ...
    def judge(self, req: TenderRequirement, answers: list[QuestionAnswer]) -> Judgement
    def evaluate(self, tender) -> EligibilitySummary       # applique judge à toutes les exigences, persiste, RB-003
```
- Règles par catégorie (`judge`) :
  - `certification` : nom de certification détecté dans `description` (fuzzy ≥ 85 contre les certifications entreprise) ⇒ valide → `CONFORME` (evidence certification) ; expirée → `NON_CONFORME` « certification X expirée le … » ; absente → `INFO_MANQUANTE`.
  - `technique` : technologies/compétences citées trouvées → `CONFORME` si toutes, `A_VERIFIER` si partielles, `INFO_MANQUANTE` si aucune n'est détectable.
  - `experience` : regex `(\d+)\s*(ans|années|projets|références)` ; compare aux projets du secteur (nombre) ou à l'ancienneté max des experts → `CONFORME` / `NON_CONFORME` (avec chiffres) / `INFO_MANQUANTE` si rien de comparable.
  - `equipe` : rôle demandé fuzzy contre `Expert.role` → `CONFORME` (evidence expert) sinon `INFO_MANQUANTE`.
  - `administrative` / `financiere` / `juridique` : `CompanyDocument.is_usable` de la catégorie correspondante (`administratif`/`attestation`, `financier`, `juridique`) dont `name`/`tags` matchent un mot de la description → `CONFORME` (evidence document) ; document présent mais expiré → `NON_CONFORME` ; sinon `INFO_MANQUANTE`.
  - `methodologie` / `autre` : `A_VERIFIER`.
  - Une réponse utilisateur (`answers`) liée à l'exigence prime : réponse contenant « oui » → `CONFORME` (evidence answer) ; « non » → `NON_CONFORME` ; autre → `A_VERIFIER`. (Le raffinement LLM+RAG arrive en 8.4.)
- `evaluate` : persiste `status/justification/evidence`, calcule le résumé, écrit `tender.extra["eligibility"] = summary`, relance le scoring (`ScoreService.score_tender`) avec `eligibility_ratio`, et pour chaque exigence obligatoire `NON_CONFORME|INFO_MANQUANTE` appelle `NotificationService.notify(kind="mandatory_unmet", …)` (service créé en Phase 11 ; jusque-là un hook `on_mandatory_unmet: Callable` par défaut journalise).

- [ ] **Step 1 : Tests** : un cas par catégorie (≥ 8 tests) ; `ratio` ; `mandatory_unmet` contient le code d'une exigence obligatoire manquante ; réponse « Oui, 2 experts » ⇒ `CONFORME`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(eligibility): rule-based eligibility engine, RB-003 flagging, score refresh`.

---

### Task 7.3 : Questions intelligentes et réponses

**Files:**
- Create: `backend/app/models/question.py`, `backend/app/ai/prompts/question_generate.py`, `backend/app/services/questions.py`, `backend/app/api/v1/questions.py`, `backend/alembic/versions/0011_questions.py`
- Modify: `backend/app/ai/outputs.py` (`QuestionOutput`), `backend/app/workers/tasks/eligibility.py` (génère les questions après `evaluate`), `backend/app/api/router.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_questions.py`, `backend/tests/api/test_questions_api.py`

**Interfaces:**
- Produces: `Question`, `QuestionAnswer` (section 2) ; `QuestionOutput(text: str, priority: Priority)` ; `QuestionService(db, llm)` : `generate(tender) -> list[Question]` (une question par exigence `INFO_MANQUANTE` ou `A_VERIFIER` sans question ouverte ; priorité forcée `CRITIQUE` si `is_mandatory`, sinon celle du LLM ; le prompt reçoit l'exigence + ce que l'entreprise possède déjà pour formuler une question précise — ex. « L'appel d'offres exige un expert cybersécurité avec 8 ans d'expérience ; votre expert le plus expérimenté en a 5. Disposez-vous d'un autre profil ? ») ; `answer(question, text, user_id) -> QuestionAnswer` (statut `answered`, audit `question.answered`, ré-évalue l'exigence liée via `EligibilityEngine.judge` avec la réponse) ; `skip(question)`.
- Endpoints : `GET /tenders/{id}/questions?status=` (tri : CRITIQUE > IMPORTANTE > FACULTATIVE) ; `POST /tenders/{id}/questions/generate` ; `POST /questions/{id}/answer {answer}` ; `POST /questions/{id}/skip`.

- [ ] **Step 1 : Tests** : 3 exigences (`CONFORME`, `INFO_MANQUANTE` obligatoire, `A_VERIFIER`) ⇒ 2 questions, la première `CRITIQUE` ; répondre « Oui » ⇒ exigence `CONFORME` et question `answered` ; regénérer ne duplique pas les questions ouvertes.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(questions): targeted question generation and answers feeding eligibility`.

---

### Task 7.4 : Frontend — pages Exigences / Éligibilité et Questions

**Files:**
- Create: `frontend/src/components/tenders/RequirementsTable.tsx`, `EligibilitySummary.tsx`, `QuestionsList.tsx`, `frontend/src/lib/queries/{requirements,questions}.ts`
- Modify: `frontend/src/app/(app)/tenders/[id]/page.tsx` (onglets Exigences, Questions)
- Test: `frontend/tests/RequirementsTable.test.tsx`

**Interfaces:**
- Produces: `RequirementsTable` (code, catégorie, description, obligatoire, preuve, statut avec badge : CONFORME vert / A_VERIFIER orange / NON_CONFORME rouge / INFO_MANQUANTE gris, source `doc p. N`, justification, preuves cliquables ; filtres ; édition inline du statut ; bandeau rouge « N exigences obligatoires non satisfaites » — RB-003) ; `EligibilitySummary` (compteurs par statut, ratio) ; `QuestionsList` (groupées par priorité, formulaire de réponse, « Ignorer », bouton « Générer les questions »).

- [ ] **Step 1 : Test** : bandeau RB-003 affiché quand `mandatory_unmet.length > 0`. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): requirements, eligibility and questions tabs`.

**Fin de Phase 7 — critères :** exigences extraites au format `TECH-001` avec source ; comparaison avec profil et documents ; une information manquante déclenche une question ; réponse ⇒ statut mis à jour (CdC §35).

---
# PHASE 8 — Base de connaissances & RAG (S9)

### Task 8.1 : Indexation des documents entreprise + résumé IA du profil

**Files:**
- Create: `backend/app/ai/prompts/company_summary.py`, `backend/app/workers/tasks/knowledge.py`
- Modify: `backend/app/services/documents.py` (`upload`/`new_version` enfilent `index_document(kind="company_document")`), `backend/app/api/v1/company.py` (`PUT /company/profile` et CRUD enfilent `refresh_company_summary`), `backend/app/workers/celery_app.py`
- Test: `backend/tests/workers/test_knowledge_tasks.py`

**Interfaces:**
- Produces: tâche `refresh_company_summary(db, job)` → `CompanyProfile.ai_summary` (≤ 300 mots, généré depuis identité + secteurs + compétences + technologies + certifications valides + experts + projets ; prompt interdit d'ajouter des faits) ; `company_facts(db) -> CompanyFacts` (Pydantic : listes structurées des mêmes données, utilisé par le scoring, l'éligibilité et la génération comme **unique source de faits**) ; les documents entreprise sont indexés avec `owner_kind="company_document"` et `metadata={"category", "name", "expires_at", "version"}`.

- [ ] **Step 1 : Tests** : upload d'un document ⇒ un job `index_document` enfilé (vérifier via `JobService.list(type="index_document")` avec `run_jobs_inline`) ; `refresh_company_summary` avec `FakeLLM(text_responses=["Résumé"])` ⇒ `ai_summary == "Résumé"`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(knowledge): index company documents, AI profile summary, CompanyFacts`.

---

### Task 8.2 : Service de base de connaissances (recherche sémantique filtrée, contexte RAG)

**Files:**
- Create: `backend/app/services/knowledge.py`
- Test: `backend/tests/unit/test_knowledge.py`

**Interfaces:**
- Produces:

```python
class KBHit(BaseModel):
    chunk_id: UUID; owner_kind: str; owner_id: UUID; document_name: str; page: int | None; content: str; score: float; metadata: dict

class KnowledgeBase:
    def __init__(self, db, embeddings): ...
    def search(self, query: str, *, owner_kind: str | None = None, tender_id: UUID | None = None,
               categories: list[str] | None = None, usable_only: bool = True, k: int = 8) -> list[KBHit]
    def build_context(self, hits: list[KBHit], *, max_chars: int = 8000) -> str   # "[S1] (Kbis.pdf p.2) …\n[S2] …"
```
- `usable_only=True` joint `company_documents` et exclut `status != valid` ou `expires_at < today` (RB-007) ; `tender_id` limite aux chunks des documents de cet AO ; `score = 1 - cosine_distance` ; SQL : `ORDER BY embedding <=> :vec LIMIT k`.

- [ ] **Step 1 : Tests** : avec `FakeEmbeddings` (déterministe), insérer 3 chunks dont un sur un document expiré ⇒ `search(usable_only=True)` ne le renvoie pas ; `build_context` numérote `[S1]…` et respecte `max_chars`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(knowledge): filtered semantic search and RAG context builder`.

---

### Task 8.3 : Recherche interne (Module 18)

**Files:**
- Create: `backend/app/services/internal_search.py`, `backend/app/api/v1/search.py`, `frontend/src/app/(app)/search/page.tsx`, `frontend/src/components/search/SearchResults.tsx`
- Modify: `backend/app/api/router.py`, `frontend/src/components/layout/Sidebar.tsx` (raccourci `Ctrl+K` ouvrant la recherche)
- Test: `backend/tests/api/test_internal_search.py`, `frontend/tests/SearchResults.test.tsx`

**Interfaces:**
- Produces: `GET /search?q=&kinds=tenders,documents,projects,experts,references,certifications&semantic=true` → `{"groups": [{"kind": "tenders", "items": [{"id","title","subtitle","url","score"}]}, …]}` ; texte : `ILIKE %q%` sur les champs nom/titre/description ; sémantique : `KnowledgeBase.search(q, k=10)` groupé par document (meilleur score) + `Tender.embedding` cosinus pour « projets similaires à une demande donnée » ; `url` = route frontend (`/tenders/{id}`, `/documents?open={id}`, `/company?tab=projects&id=…`).

- [ ] **Step 1 : Tests** : `q=cyber` trouve un projet dont la description contient « cybersécurité » ; réponse groupée par `kind`. **Step 2 :** FAIL. **Step 3 :** implémenter (page front : champ de recherche, résultats groupés, navigation). **Step 4 :** PASS. **Step 5 : Commit** `feat(search): internal text + semantic search`.

---

### Task 8.4 : Éligibilité étayée par RAG (raffinement des `A_VERIFIER`)

**Files:**
- Create: `backend/app/ai/prompts/eligibility_judge.py`
- Modify: `backend/app/ai/outputs.py` (`EligibilityJudgement`), `backend/app/services/eligibility.py` (`EligibilityEngine(db, company, kb=None, llm=None)` ; après les règles, pour chaque `A_VERIFIER`/`INFO_MANQUANTE` : `kb.search(req.description, owner_kind="company_document", k=5)` → LLM → statut raffiné), `backend/app/workers/tasks/eligibility.py` (injecte `kb` et `llm`)
- Test: `backend/tests/unit/test_eligibility_rag.py`

**Interfaces:**
- Produces: `EligibilityJudgement(status: RequirementStatus, justification: str, evidence_refs: list[str])` (`evidence_refs` = identifiants `S1…` du contexte) ; **garde-fou** : le LLM ne peut produire `CONFORME` que si `evidence_refs` est non vide et pointe vers des hits existants — sinon rétrogradé en `A_VERIFIER` avec justification « preuve non fournie » ; les `Evidence(kind="chunk")` persistées portent `chunk_id`, `document_name`, `page`.

- [ ] **Step 1 : Tests** : hit sur « Attestation ISO 27001 valide jusqu'en 2027 » + `FakeLLM` répondant `CONFORME` avec `["S1"]` ⇒ `CONFORME` avec evidence `chunk` ; `FakeLLM` répondant `CONFORME` avec `[]` ⇒ `A_VERIFIER`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(eligibility): RAG-backed judgement with evidence guard`.

---

### Task 8.5 : Frontend — preuves et sources

**Files:**
- Modify: `frontend/src/components/tenders/RequirementsTable.tsx` (popover « Preuves » : liste des `evidence` avec lien vers le document/page ou l'entité du profil), `frontend/src/components/documents/DocumentDrawer.tsx` (statut d'indexation, bouton « Réindexer »)
- Test: `frontend/tests/EvidencePopover.test.tsx`

- [ ] **Step 1 : Test** : une preuve `kind: "chunk"` affiche « Kbis.pdf — p. 2 ». **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): evidence popover, reindex action`.

**Fin de Phase 8 — critères :** les documents validés alimentent la KB ; la recherche interne retrouve un projet similaire ; une exigence peut être `CONFORME` avec une preuve documentaire citée.

---

# PHASE 9 — Génération des documents de candidature (S10)

### Task 9.1 : Modèles templates / applications / documents / sections + migration

**Files:**
- Create: `backend/app/models/template.py`, `backend/app/models/application.py`, `backend/alembic/versions/0012_applications.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/tender.py` (relation `application`)

**Interfaces:**
- Produces: `Template` (+ `DocumentType` enum : `presentation, lettre_candidature, offre_technique, methodologie, comprehension_besoin, organisation_planning, equipe, cv, references, declaration`), `Application` (+ `ApplicationStatus`), `ApplicationDocument` (+ `AppDocStatus`), `ApplicationSection` (+ `SectionStatus`) — colonnes section 2. `Template.sections` JSON = `list[{"key": str, "title": str, "instructions": str, "max_words": int, "requires": list["company_facts"|"tender_analysis"|"requirements"|"answers"|"kb"]}]`.

- [ ] **Step 1 :** modèles + migration + test `test_application_unique_per_tender`. **Step 2 :** PASS. **Step 3 : Commit** `feat(applications): templates, applications, documents, sections models`.

---

### Task 9.2 : Templates par défaut (seed) + endpoints

**Files:**
- Create: `backend/app/services/templates.py` (`DEFAULT_TEMPLATES`, `seed_templates(db)`), `backend/app/api/v1/templates.py`
- Modify: `backend/app/cli.py` (`seed-templates`), `backend/app/api/router.py`
- Test: `backend/tests/unit/test_templates_seed.py`, `backend/tests/api/test_templates_api.py`

**Interfaces:**
- Produces: 10 templates par défaut (`is_default=True`, `language="fr"`, `version=1`). Sections attendues :
  - `presentation` : identité & chiffres clés · secteurs & expertises · certifications (valides uniquement) · références marquantes · pourquoi nous pour cet AO.
  - `lettre_candidature` : objet & référence de l'AO · déclaration d'intérêt · synthèse de l'adéquation · engagements & signature.
  - `offre_technique` : contexte & enjeux · périmètre proposé · architecture / solution · livrables · hypothèses & limites.
  - `methodologie` : approche générale · phases & jalons · pilotage & qualité · gestion des risques.
  - `comprehension_besoin` : reformulation du besoin · objectifs & résultats attendus · contraintes identifiées · points d'attention.
  - `organisation_planning` : organisation projet · planning macro (tableau) · charge par phase · gouvernance.
  - `equipe` : composition (tableau rôle / nom / expérience) · rôles & responsabilités · disponibilité.
  - `cv` : une section par expert sélectionné (profil, expériences pertinentes, compétences, certifications, formation) — template « répétable » (`repeat_for: "experts"`).
  - `references` : une section par projet pertinent (client, contexte, périmètre, technologies, résultats) — `repeat_for: "projects"`.
  - `declaration` : identification · déclarations sur l'honneur (texte standard, champs `[À COMPLÉTER]` pour les données non disponibles).
- Endpoints : `GET /templates`, `POST /templates`, `GET/PATCH /templates/{id}` (validation : clés de section uniques).

- [ ] **Step 1 : Tests** : `seed_templates` idempotent (2 appels ⇒ 10 templates) ; `PATCH` avec clés dupliquées ⇒ 422. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(templates): default templates seed and endpoints`.

---

### Task 9.3 : Service de génération contrôlée (contexte, prompt, garde anti-invention)

**Files:**
- Create: `backend/app/services/generation_context.py`, `backend/app/services/fact_guard.py`, `backend/app/ai/prompts/section_generate.py`, `backend/app/services/generation.py`
- Modify: `backend/app/ai/outputs.py` (`SectionOutput`)
- Test: `backend/tests/unit/test_generation_context.py`, `test_fact_guard.py`, `test_generation.py`

**Interfaces:**
- Produces:

```python
class GenerationContext(BaseModel):
    company: CompanyFacts                      # Task 8.1 — uniquement certifications valides, documents usable
    tender: dict                               # TenderAnalysisOut + titre/organisme/référence/deadline
    requirements: list[dict]                   # code, description, is_mandatory, status, justification
    answers: list[dict]                        # question + réponse
    kb_context: str                            # KnowledgeBase.build_context(...)
    kb_hits: list[KBHit]
    template_instructions: str
def build_context(db, kb, tender, section_spec, *, repeat_item=None) -> GenerationContext   # kb.search(section.title + tender.object, owner_kind="company_document", k=6)

class SectionOutput(BaseModel):
    content_md: str; used_sources: list[str]; missing_info: list[str]

class FactGuard:
    def check(self, content_md: str, facts: CompanyFacts) -> list[str]   # avertissements
```
- Prompt système (`PROMPT_VERSION="v1"`) : rôle rédacteur de réponse à AO ; règles : n'utiliser QUE les faits fournis (`company`, `answers`, `kb_context`) ; toute donnée absente ⇒ écrire `[À COMPLÉTER : …]` et la lister dans `missing_info` ; ne jamais inventer certification, référence, chiffre, date, nom ; citer `[S1]` quand une source KB est utilisée ; répondre en français, Markdown, ≤ `max_words`.
- `FactGuard.check` : détecte dans `content_md` (a) les motifs `ISO\s?\d{4,5}|CMMI|ITIL|PMP|PRINCE2|SOC\s?2|HDS|RGS` absents des certifications valides ; (b) les années d'expérience `(\d+)\s*ans` supérieures à l'ancienneté max connue ; (c) les noms de clients cités absents de `projects`/`references` (majuscule + fuzzy < 80) ⇒ avertissements « Élément non vérifié : … ». Ne bloque pas ; stockés dans `ApplicationDocument.warnings` et affichés (RB-005).
- `GenerationService(db, llm, kb).generate_document(doc: ApplicationDocument, *, on_progress) -> ApplicationDocument` : pour chaque section du template (répétée si `repeat_for`), `build_context` → `llm.structured(tier="strong", output=SectionOutput)` → `ApplicationSection(status="generated", sources=[hits utilisés], missing_info)` ; échec d'une section ⇒ section `content_md="[Génération échouée : …]"` et poursuite ; `doc.status = draft`, `warnings = FactGuard`. `regenerate_section(section, instruction: str | None)` réutilise le contexte + instruction utilisateur + contenu précédent.

- [ ] **Step 1 : Tests** : `build_context` n'inclut pas une certification expirée ni un document expiré ; `FactGuard` signale « ISO 14001 » absente ; génération de 3 sections avec `FakeLLM` ⇒ 3 `ApplicationSection` `generated` avec `sources` ; une section dont le LLM lève ⇒ contenu « [Génération échouée » et document `draft`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(generation): controlled section generation with sources and fact guard`.

---

### Task 9.4 : Job de génération, endpoints dossier de candidature, export DOCX

**Files:**
- Create: `backend/app/services/applications.py`, `backend/app/services/docx_export.py`, `backend/app/workers/tasks/generation.py`, `backend/app/api/v1/applications.py`, `backend/app/schemas/application.py`
- Modify: `backend/app/workers/celery_app.py`, `backend/app/api/router.py`
- Test: `backend/tests/unit/test_docx_export.py`, `backend/tests/api/test_applications_api.py`

**Interfaces:**
- Produces: `ApplicationService(db)` : `create_for_tender(tender, user_id) -> Application` (exige statut `GO`/`PREPARATION` ; passe le tender en `PREPARATION`), `add_documents(app, template_ids) -> list[ApplicationDocument]` (titre = `f"{template.name} — {tender.title[:60]}"`), `mark_ready(app, user_id)` (Phase 10) ; tâche `generate_application_documents(db, job, *, application_id, document_ids: list[str] | None)` (progress par document ; statut `generating` → `draft`/`failed` ; `application.status = review` ; audit `application.generated` ; notification `validation_required` en Phase 11) ; `export_docx(doc: ApplicationDocument, company: CompanyFacts) -> bytes` (python-docx : page de garde titre/entreprise/AO/date, un titre H1 par section, Markdown → paragraphes/listes/tableaux simples/gras ; pied de page « Document généré avec assistance IA — validé le … » uniquement si validé) ; export stocké sous `applications/{app_id}/{doc_id}-v{n}.docx`.
- Endpoints : `POST /tenders/{id}/application` (201) ; `GET /applications/{id}` (documents + sections + statuts + warnings) ; `POST /applications/{id}/documents {template_ids}` ; `POST /applications/{id}/generate {document_ids?}` → 202 job ; `GET /applications/{id}/documents/{docId}` ; `POST …/export` → régénère le DOCX de la version courante ; `GET …/download`.

- [ ] **Step 1 : Tests** : `export_docx` produit un fichier ouvrable par python-docx avec autant de H1 que de sections ; `POST /tenders/{id}/application` sur un tender `NOUVEAU` ⇒ 422 `invalid_transition` ; flux complet avec `run_jobs_inline` + `FakeLLM` ⇒ `GET /applications/{id}` renvoie un document `draft` avec sections.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(applications): generation job, application endpoints, DOCX export`.

---

### Task 9.5 : Frontend — page Génération des documents de candidature

**Files:**
- Create: `frontend/src/components/applications/ApplicationPanel.tsx`, `TemplatePicker.tsx`, `DocumentStatusList.tsx`, `frontend/src/lib/queries/applications.ts`
- Modify: `frontend/src/app/(app)/tenders/[id]/page.tsx` (onglet Candidature)
- Test: `frontend/tests/TemplatePicker.test.tsx`

**Interfaces:**
- Produces: bouton « Créer le dossier de candidature » (visible si statut `GO`) ; `TemplatePicker` (cases à cocher des templates, présélection depuis `analysis.requested_documents` par correspondance de mots-clés) ; « Générer » → `JobProgress` ; `DocumentStatusList` (statut par document, avertissements FactGuard, nombre de `[À COMPLÉTER]`, liens « Éditer » (Phase 10) et « Télécharger DOCX »).

- [ ] **Step 1 : Test** : `TemplatePicker` présélectionne « Offre technique » quand un document demandé contient « offre technique ». **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): application creation and generation panel`.

**Fin de Phase 9 — critères :** les principaux documents sont générés à partir des données validées, avec sources et zones `[À COMPLÉTER]` explicites ; export DOCX téléchargeable.

---

# PHASE 10 — Validation humaine & gestion des versions (S10)

### Task 10.1 : Actions par section (éditer, régénérer, accepter, rejeter, commenter)

**Files:**
- Create: `backend/app/services/review.py`, `backend/app/api/v1/sections.py`
- Modify: `backend/app/workers/tasks/generation.py` (tâche `regenerate_section`), `backend/app/api/router.py`
- Test: `backend/tests/api/test_sections_api.py`

**Interfaces:**
- Produces: `ReviewService(db)` : `edit(section, content_md, comment, user_id)` (statut `edited`, audit `section.edited`), `accept(section)` (`validated`), `reject(section, comment)` (`rejected`), `request_regeneration(section, instruction) -> Job` (job `regenerate_section` → nouveau contenu, statut `generated`, audit `section.regenerated`, conserve l'ancien contenu dans `section.sources["previous"]` pour le diff).
- Endpoints : `PATCH /sections/{id} {content_md?, comment?}` ; `POST /sections/{id}/regenerate {instruction?}` → 202 ; `POST /sections/{id}/accept` ; `POST /sections/{id}/reject {comment}`.
- Règle : toute action sur une section d'un document `validated` ⇒ 409 `document_validated` (il faut créer une nouvelle version, Tâche 10.2).

- [ ] **Step 1 : Tests** : édition ⇒ `edited` + audit ; régénération avec `FakeLLM` ⇒ contenu remplacé, `previous` conservé ; action sur document validé ⇒ 409.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(review): per-section edit, regenerate, accept, reject`.

---

### Task 10.2 : Validation du document (RB-006), versions V1…Vn, restauration, dossier prêt

**Files:**
- Modify: `backend/app/services/review.py`, `backend/app/services/applications.py`, `backend/app/api/v1/applications.py`
- Test: `backend/tests/api/test_validation_api.py`

**Interfaces:**
- Produces: `ReviewService.validate_document(doc, user_id) -> DocumentVersion` : exige toutes les sections `validated` (sinon 422 `sections_not_validated` avec la liste des clés), et aucune occurrence de `[À COMPLÉTER` (sinon 422 `missing_info_remaining`) ; exporte le DOCX, crée `DocumentVersion(document_kind="application", version_number=doc.current_version, author=user.email, changelog=commentaires agrégés)`, `doc.status = validated`, audit `application_document.validated` ; `new_version(doc)` : `current_version += 1`, sections repassent en `edited`, statut `draft` ; `restore_version(doc, n)` : recharge le DOCX de la version `n` en tant que nouvelle version (le contenu des sections est stocké en JSON dans `DocumentVersion.changelog`-compagnon `sections_snapshot` — ajouter la colonne JSON `snapshot` à `document_versions` par migration `0013_version_snapshot`) ; `ApplicationService.mark_ready(app, user_id)` : exige tous les documents `validated`, `application.status = ready`, tender `VALIDATION → PRET` via `transition`.
- Endpoints : `POST /applications/{id}/documents/{docId}/validate` ; `GET …/versions` ; `POST …/versions/{n}/restore` ; `POST /applications/{id}/ready`. Passage automatique du tender en `VALIDATION` dès la première génération terminée (Tâche 9.4 : `PREPARATION → VALIDATION`).

- [ ] **Step 1 : Tests** : validation avec une section `generated` ⇒ 422 ; avec `[À COMPLÉTER` ⇒ 422 ; validation OK ⇒ version 1 + DOCX présent ; `new_version` ⇒ 2 ; `restore 1` ⇒ version 3 avec le contenu de la 1 ; `ready` ⇒ tender `PRET`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(review): document validation RB-006, versions and restore, application ready`.

---

### Task 10.3 : Frontend — page Édition / validation

**Files:**
- Create: `frontend/src/app/(app)/applications/[id]/documents/[docId]/page.tsx`, `frontend/src/components/applications/SectionEditor.tsx`, `SectionToolbar.tsx`, `VersionHistory.tsx`, `DiffView.tsx`, `frontend/src/lib/queries/sections.ts`
- Test: `frontend/tests/SectionToolbar.test.tsx`

**Interfaces:**
- Produces: page à deux colonnes — sommaire des sections avec pastilles de statut à gauche, éditeur Markdown (textarea + aperçu, `react-markdown` à ajouter) à droite ; `SectionToolbar` : Enregistrer · Régénérer (dialogue d'instruction) · Accepter · Rejeter (commentaire) ; encart « Sources utilisées » (`[S1]` → document/page) et « Informations manquantes » ; `DiffView` (avant/après régénération, via `diff` npm) ; en-tête : « Valider le document » (désactivé tant que des sections ne sont pas validées, tooltip listant lesquelles), « Nouvelle version », `VersionHistory` (V1…Vn, télécharger, restaurer) ; bandeau des avertissements FactGuard ; bouton « Dossier prêt » sur l'onglet Candidature.

- [ ] **Step 1 : Test** : « Valider le document » désactivé si une section est `generated`. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): section editor, validation and version history`.

**Fin de Phase 10 — critères :** l'utilisateur peut modifier, régénérer, commenter et valider chaque section/document ; versions conservées et restaurables ; aucun document n'est « final » sans validation (RB-006).

---
# PHASE 11 — Dashboard, notifications, échéances, historique (S11)

### Task 11.1 : Notifications (modèle, service, déclencheurs, email)

**Files:**
- Create: `backend/app/models/notification.py`, `backend/app/services/notifications.py`, `backend/app/connectors/email/base.py`, `email/resend.py`, `email/fake.py`, `backend/app/api/v1/notifications.py`, `backend/alembic/versions/0014_notifications.py`
- Modify: `backend/app/core/deps.py` (`get_email()`), `backend/app/services/score_service.py` (≥ seuil ⇒ `new_relevant_tender`), `eligibility.py` (`mandatory_unmet`), `questions.py` (`missing_info`), `workers/tasks/generation.py` (`validation_required`), `workers/tracking.py` (`job_failed`), `workers/tasks/scheduled.py` (tâches `notify_deadlines` 07:00 UTC et `notify_expiring_certifications` 07:10 UTC), `backend/app/api/router.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_notifications.py`, `backend/tests/api/test_notifications_api.py`

**Interfaces:**
- Produces:

```python
class NotificationKind(str, enum.Enum):
    new_relevant_tender="new_relevant_tender"; deadline_soon="deadline_soon"; missing_document="missing_document"
    missing_info="missing_info"; certification_expired="certification_expired"; validation_required="validation_required"
    mandatory_unmet="mandatory_unmet"; job_failed="job_failed"
class NotificationService:
    def __init__(self, db, email: EmailProvider | None = None): ...
    def notify(self, *, kind, title, body, severity="info", entity_kind=None, entity_id=None) -> Notification | None
        # dédoublonne : même (kind, entity_kind, entity_id) déjà créée aujourd'hui ⇒ None
        # severity == "critical" et settings.notification_email ⇒ email immédiat ; sinon inclus dans le digest quotidien
    def unread_count(self) -> int
def notify_deadlines(db) -> int          # tenders actifs en GO/PREPARATION/VALIDATION/PRET avec days_left ∈ {7, 3, 1} ⇒ deadline_soon (critical si ≤ 1)
def notify_expiring_certifications(db) -> int   # certifications expirant dans ≤ 30 j ou expirées ⇒ certification_expired (warning)
def send_daily_digest(db, email) -> None         # 08:00 UTC : notifications non lues des 24 h
```
- `ResendEmail(api_key)` (`POST https://api.resend.com/emails`) ; `FakeEmail.sent: list[dict]`.
- Endpoints : `GET /notifications?unread=true&page=` ; `POST /notifications/{id}/read` ; `POST /notifications/read-all`.

- [ ] **Step 1 : Tests** : dédoublonnage (2 appels ⇒ 1 notification) ; `critical` ⇒ `FakeEmail.sent` contient 1 email ; `notify_deadlines` avec `freezegun` crée `deadline_soon` à J-3 ; `unread=true` filtre.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter (brancher les déclencheurs listés — remplacer les hooks provisoires de la Phase 7). **Step 4 :** PASS. **Step 5 : Commit** `feat(notifications): model, triggers, scheduled deadline/certification checks, email`.

---

### Task 11.2 : Dashboard, statistiques, historique, paramètres

**Files:**
- Create: `backend/app/services/dashboard.py`, `backend/app/api/v1/dashboard.py`, `backend/app/api/v1/audit.py`, `backend/app/api/v1/settings.py`, `backend/app/models/settings.py` (`AppSetting(key unique, value JSON)`), `backend/alembic/versions/0015_settings.py`
- Modify: `backend/app/api/router.py`, `backend/app/core/config.py` (les seuils lisent `AppSetting` en priorité via `get_runtime_settings(db)`)
- Test: `backend/tests/unit/test_dashboard.py`, `backend/tests/api/test_audit_api.py`

**Interfaces:**
- Produces:

```python
class DashboardOut(BaseModel):
    counts_by_status: dict[str, int]; new_this_week: int; relevant: int; go: int; no_go: int
    in_preparation: int; in_validation: int; ready_or_submitted: int; won: int; lost: int
    win_rate: float | None; avg_score: float | None; potential_value: float     # Σ budget_max des GO/PREPARATION/VALIDATION/PRET/SOUMIS
    upcoming_deadlines: list[TenderOut]   # 10 prochaines, actifs, non NO_GO/ARCHIVE
    documents_analyzed: int; documents_generated: int; unread_notifications: int
class StatsOut(BaseModel):
    tenders_per_week: list[{week: str, count: int}]; score_distribution: list[{bucket: str, count: int}]
    decisions_per_month: list[{month: str, go: int, no_go: int}]; outcomes: {won: int, lost: int, pending: int}
    by_sector: list[{sector: str, count: int, avg_score: float}]
```
- `GET /dashboard` ; `GET /stats?months=6` (calculés en direct par requêtes SQL agrégées — le job `build_report` de l'AT §7 n'est pas nécessaire aux volumes mono-utilisateur ; à introduire seulement si `GET /stats` dépasse 1 s) ; `GET /audit?entity_kind=&entity_id=&action=&from=&to=&page=` (`AuditOut` avec `user_email`) ; `GET /settings` / `PUT /settings` (`relevance_threshold`, `notification_email`, `deadline_alert_days: [7,3,1]`, `certification_alert_days: 30`) ; `GET /settings/status` (présence des clés OpenAI/Tavily/Resend sans les révéler, état Redis/stockage).

- [ ] **Step 1 : Tests** : jeu de 6 tenders dans des statuts variés ⇒ compteurs exacts, `potential_value`, `win_rate = won / (won + lost)` ; `GET /audit?action=tender.decision` filtre.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(dashboard): dashboard, stats, audit and settings endpoints`.

---

### Task 11.3 : Frontend — Dashboard, notifications, historique, statistiques, paramètres

**Files:**
- Create: `frontend/src/app/(app)/dashboard/page.tsx` (remplace le placeholder), `notifications/page.tsx`, `history/page.tsx`, `stats/page.tsx`, `settings/page.tsx`, `frontend/src/components/dashboard/StatTile.tsx`, `DeadlinesList.tsx`, `StatusBars.tsx`, `frontend/src/components/layout/NotificationBell.tsx`, `frontend/src/lib/queries/{dashboard,notifications,audit,settings}.ts`
- Modify: `frontend/src/components/layout/Sidebar.tsx` (cloche + compteur non lus, polling 60 s)
- Test: `frontend/tests/StatTile.test.tsx`, `frontend/tests/NotificationBell.test.tsx`

**Interfaces:**
- Produces: Dashboard = tuiles (nouvelles, pertinentes, GO, en préparation, en validation, prêtes/soumises, gagnées/perdues, valeur potentielle) + `DeadlinesList` (urgence colorée) + `StatusBars` (répartition par statut) + dernières notifications ; page Notifications (liste, marquer lu, lien vers l'entité) ; page Historique (table filtrable action/entité/date, payload dépliable) ; page Statistiques (graphiques `recharts` : tenders par semaine, distribution des scores, GO/NO-GO par mois, résultats, par secteur — charger le skill `dataviz` avant d'écrire ces graphiques) ; page Paramètres (formulaire des seuils/email, état des intégrations).

- [ ] **Step 1 : Tests** : `StatTile` rend libellé + valeur ; `NotificationBell` affiche le badge quand `unread > 0`. **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS. **Step 5 : Commit** `feat(frontend): dashboard, notifications, history, stats, settings pages`.

**Fin de Phase 11 — critères :** échéances et urgences visibles ; notifications (pertinente, échéance, info manquante, certification expirée, validation requise) en UI et par email ; historique des actions principales consultable (CdC §35).

---

# PHASE 12 — Sécurité, tests E2E, sauvegardes, observabilité, déploiement (S12)

### Task 12.1 : Durcissement sécurité

**Files:**
- Create: `backend/app/core/security_headers.py`, `docs/07-securite.md`
- Modify: `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/v1/documents.py` & `tender_documents.py` (vérification `filetype.guess` en plus de l'extension), `frontend/next.config.ts` (headers)
- Test: `backend/tests/api/test_security.py`

**Interfaces:**
- Produces: middleware ajoutant `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Strict-Transport-Security` (prod) ; `cookie_secure=True` en `staging|prod` ; rate-limit global `120/minute` et `5/minute` sur login ; taille max de requête ; `TrustedHostMiddleware` avec `allowed_hosts` ; réponses d'erreur sans stack trace en prod ; journalisation des opérations sensibles (login échoué, téléchargement de document, changement de paramètres) via `record_audit` ; téléchargements servis uniquement via l'API authentifiée (jamais d'URL de stockage exposée).
- `docs/07-securite.md` : menaces considérées, mesures, gestion des secrets (Railway variables, jamais dans Git), rotation des clés, données personnelles des CV (accès restreint, minimisation vers l'IA : seuls les extraits nécessaires sont envoyés), procédure en cas d'incident.

- [ ] **Step 1 : Tests** : en-têtes présents ; 6 logins échoués en 1 min ⇒ 429 ; un fichier `.pdf` dont le contenu est un exécutable ⇒ 422 ; `GET /documents/{id}/download` sans cookie ⇒ 401.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter + rédiger le doc. **Step 4 :** PASS. **Step 5 : Commit** `feat(security): headers, rate limits, content sniffing, security doc`.

---

### Task 12.2 : Tests E2E Playwright (parcours critique) et plan de tests

**Files:**
- Create: `frontend/e2e/playwright.config.ts`, `frontend/e2e/critical-path.spec.ts`, `backend/app/api/v1/testing.py` (routes `POST /testing/reset` et `POST /testing/seed` actives uniquement si `APP_ENV=test`), `docs/09-plan-tests.md`
- Modify: `.github/workflows/ci.yml` (job `e2e` : compose postgres/redis, backend en `APP_ENV=test` avec fakes, front `next build && next start`, `npx playwright test`)

**Interfaces:**
- Produces: en `APP_ENV=test`, `deps.get_llm()` renvoie un `ScriptedLLM` qui répond selon le type de sortie demandé (candidat AO, analyse, exigences, score, questions, sections) avec des données fixes réalistes ; `POST /testing/seed` crée utilisateur, profil InnoSustain, 1 source fake, templates.
- Scénario `critical-path.spec.ts` : login → profil (vérifier InnoSustain) → lancer une recherche → 1 opportunité apparaît avec score → GO → analyser → 3 exigences visibles → répondre à une question → créer le dossier → générer 2 documents → éditer une section → accepter toutes les sections → valider le document → « Dossier prêt » → statut `PRET` sur le Kanban → entrée dans l'historique.
- `docs/09-plan-tests.md` : pyramide (unitaires services / API / workers / composants / E2E), commandes, couverture cible (backend ≥ 80 % sur `services/` et `api/`), stratégie de fakes, jeux de fixtures.

- [ ] **Step 1 :** écrire le scénario (échoue). **Step 2 :** implémenter `ScriptedLLM`, routes de test, ajustements. **Step 3 :** `npx playwright test` → PASS localement et en CI. **Step 4 : Commit** `test(e2e): critical path scenario, scripted LLM, test plan doc`.

---

### Task 12.3 : Sauvegardes et restauration

**Files:**
- Create: `infrastructure/scripts/backup.sh`, `infrastructure/scripts/restore.sh`, `backend/app/workers/tasks/scheduled.py` (tâche `nightly_backup` 03:00 UTC si `BACKUP_ENABLED=true`)
- Modify: `docs/08-deploiement.md` (section sauvegarde)

**Interfaces:**
- Produces: `backup.sh` : `pg_dump -Fc` → `backups/tender-YYYYMMDD-HHMM.dump` → `aws s3 cp` vers `s3://<bucket>/backups/` (endpoint R2), rétention 30 jours ; les documents sont déjà dans le stockage objet (activer le versioning du bucket R2) ; `restore.sh <dump>` : `pg_restore --clean --if-exists`. Procédure de restauration **testée** sur une base vide avant la mise en production, résultat consigné dans le doc.

- [ ] **Step 1 :** écrire les scripts ; **Step 2 :** exécuter backup puis restore sur `tender_test` et vérifier `select count(*) from tenders` ; **Step 3 :** documenter ; **Step 4 : Commit** `ops: backup and restore scripts, nightly backup task`.

---

### Task 12.4 : Observabilité (Sentry, logs structurés, métriques)

**Files:**
- Modify: `backend/app/main.py` (`sentry_sdk.init(dsn, environment, traces_sample_rate=0.1)` si DSN), `backend/app/workers/celery_app.py` (intégration Celery Sentry), `frontend/` (`@sentry/nextjs` init), `backend/app/services/metrics.py` (`record_metric(name, value, tags)` → table `metrics` légère ou logs), `backend/app/api/v1/settings.py` (`GET /settings/metrics` : durée moyenne des jobs par type, erreurs par source (7 j), documents analysés, temps moyen d'analyse, statut des jobs)
- Test: `backend/tests/api/test_metrics.py`

- [ ] **Step 1 : Test** : après 2 jobs (1 done, 1 failed) `GET /settings/metrics` renvoie `jobs.failed == 1`. **Step 2 :** FAIL. **Step 3 :** implémenter (chaque job journalise `job.done` avec `duration_ms` ; chaque source journalise `source.error`). **Step 4 :** PASS. **Step 5 : Commit** `feat(observability): sentry, job metrics endpoint`.

---

### Task 12.5 : Déploiement Railway (staging + prod), CI/CD

**Files:**
- Create: `railway.toml` (ou config par service via l'UI Railway : `api`, `worker`, `beat`, `frontend`, plugins PostgreSQL + Redis), `.github/workflows/deploy.yml`, `docs/08-deploiement.md`
- Modify: `infrastructure/docker/backend.Dockerfile` (image prod : `CMD` par service via variable `SERVICE_CMD`), `backend/app/main.py` (`/api/v1/health` vérifie DB + Redis + stockage : `{"status":"ok","db":true,"redis":true,"storage":true}`)

**Interfaces:**
- Produces: environnements `staging` (branche `develop`) et `production` (branche `main`), variables séparées, base isolée par environnement ; `deploy.yml` : après CI verte, `railway up --service <svc>` pour chaque service ; migration `alembic upgrade head` exécutée au démarrage de l'API (`entrypoint.sh`) ; extension `vector` activée sur la base Railway (`CREATE EXTENSION vector` — vérifier que le plugin le permet, sinon image `pgvector` en service Docker) ; HTTPS fourni par Railway ; stockage R2 avec CORS fermé ; Playwright : le worker utilise une image incluant chromium (`--with-deps`).
- `docs/08-deploiement.md` : architecture déployée, variables par environnement (sans valeurs), procédure de déploiement, rollback (`railway rollback`), sauvegarde/restauration, checklist de mise en production (utilisateur créé, templates seedés, DSN Sentry, email de notification, seuils).

- [ ] **Step 1 :** déployer en staging, lancer la checklist manuelle : login, upload d'un document, recherche réelle sur une source, analyse d'un PDF réel, génération d'un document, validation. **Step 2 :** corriger, puis déployer en prod. **Step 3 : Commit** `ops: railway deployment, deploy workflow, deployment doc`.

---

### Task 12.6 : Documentation finale et revue de couverture spec

**Files:**
- Modify: `README.md`, `docs/04-architecture-ia.md` (mettre à jour avec les prompts réels et `PROMPT_VERSION`), `docs/06-api-specification.md` (exporter `GET /api/openapi.json` en annexe)

- [ ] **Step 1 :** parcourir la matrice ci-dessous et cocher chaque ligne en vérifiant l'existence du test correspondant ; **Step 2 :** corriger les écarts ; **Step 3 : Commit** `docs: final documentation and spec coverage matrix`.

**Matrice de couverture (CdC §27 & §33) :**

| Exigence | Tâche(s) | Test(s) |
|---|---|---|
| FR-001 profil entreprise | 2.1–2.4 | `test_company.py` |
| FR-002 critères de recherche | 3.1, 3.6, 3.7 | `test_search_profiles.py` |
| FR-003 recherche automatique | 3.3–3.5 | `test_search_tenders.py` |
| FR-004 collecte des sources | 3.3, 3.5 | `test_httpx_crawler.py`, `test_rss.py` |
| FR-005 normalisation | 4.1 | `test_normalize.py` |
| FR-006 doublons | 4.2, 4.3 | `test_dedup.py`, `test_ingest.py` |
| FR-007 / FR-008 score + explication | 5.2, 5.3 | `test_scoring.py`, `test_scoring_task.py` |
| FR-009 décision GO/NO-GO | 5.4 | `test_tender_status.py` |
| FR-010 documents associés | 6.1 | `test_tender_documents.py` |
| FR-011 analyse | 6.2–6.4 | `test_extraction.py`, `test_analysis_service.py` |
| FR-012 exigences | 7.1 | `test_requirements_service.py` |
| FR-013 éligibilité | 7.2, 8.4 | `test_eligibility.py`, `test_eligibility_rag.py` |
| FR-014 / FR-015 infos manquantes, questions | 7.3 | `test_questions.py` |
| FR-016 documents entreprise | 2.3 | `test_documents_service.py` |
| FR-017 recherche documentaire | 8.2, 8.3 | `test_knowledge.py`, `test_internal_search.py` |
| FR-018 / FR-019 génération, templates | 9.2–9.4 | `test_generation.py`, `test_templates_seed.py` |
| FR-020 validation humaine | 10.1, 10.2 | `test_sections_api.py`, `test_validation_api.py` |
| FR-021 versions | 2.3, 10.2 | `test_documents_service.py`, `test_validation_api.py` |
| FR-022 échéances, notifications | 4.4, 11.1 | `test_deadlines.py`, `test_notifications.py` |
| FR-023 historique | 1.5, 11.2 | `test_audit.py`, `test_audit_api.py` |
| FR-024 dashboard | 11.2, 11.3 | `test_dashboard.py` |
| RB-001 | 4.2 | `test_dedup.py` |
| RB-002 | 4.3, 4.4 | `test_ingest.py`, `test_deadlines.py` |
| RB-003 | 7.2 | `test_eligibility.py` |
| RB-004 | 5.3 | `test_scoring_task.py` |
| RB-005 | 5.5, 9.3 (FactGuard), UI bandeaux | `test_fact_guard.py` |
| RB-006 | 10.2 | `test_validation_api.py` |
| RB-007 | 2.3, 8.2, 9.3 | `test_documents_service.py`, `test_knowledge.py`, `test_generation_context.py` |
| RB-008 | 12.1 | `test_security.py` |

---

## 6. Ordre d'exécution et jalons

```
S1  Phase 0 ──► S2  Phase 1 ──► S3  Phase 2 ──► S4  Phase 3 ──► S5  Phase 4 ──► S6  Phase 5
                                                                                     │
S12 Phase 12 ◄── S11 Phase 11 ◄── S10 Phases 9+10 ◄── S9 Phase 8 ◄── S8 Phase 7 ◄── S7 Phase 6
```

Jalons de démonstration : **M1** (fin S3) profil + documents ; **M2** (fin S6) recherche → score → GO/NO-GO ; **M3** (fin S8) analyse → exigences → questions ; **M4** (fin S10) génération → validation ; **M5** (fin S12) production.

Règles de travail :
- Une branche `feature/<phase>-<tâche>` par tâche, PR vers `develop`, `main` = production.
- Chaque tâche : test d'abord, implémentation minimale, tests verts, commit. Aucun appel réel à OpenAI/Tavily dans les tests.
- Toute nouvelle sortie IA passe par un schéma Pydantic dans `app/ai/outputs.py` et un prompt versionné dans `app/ai/prompts/`.
- Chaque nouveau modèle est importé dans `app/models/__init__.py` avant `alembic revision --autogenerate`.
- Chaque nouveau module de tâches est ajouté à `celery_app.include`.

## 7. Hors périmètre (V2, CdC §43)

Sources nombreuses / crawling avancé / API adapters (`SourceKind.api`), multilingue, OCR des PDF scannés, collaboration multi-utilisateurs, statistiques avancées, prédiction de succès, analyse concurrentielle, soumission automatique, intégrations CRM/ERP, Firecrawl, drag & drop Kanban.

