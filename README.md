# Tenders — Plateforme IA de gestion des appels d'offres

Application web mono-utilisateur pour **InnoSustain** (Innovative & Sustainable Solutions) : elle recherche et collecte les appels d'offres, les déduplique, les score, analyse leurs documents, vérifie l'éligibilité de l'entreprise, pose les questions manquantes et prépare les documents de candidature — avec validation humaine à chaque étape.

Charte : vert `#0a9a47` (marque, actions), jaune `#ffcb05` (accent), noir `#0b0f0d` (barre latérale) — définie dans `frontend/src/app/globals.css` ; logo vectoriel dans `frontend/src/components/brand/Logo.tsx`.

## Stack

| Couche | Technologie |
|---|---|
| Frontend | Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Celery |
| Données | PostgreSQL 16 + pgvector · Redis |
| Fichiers | S3-compatible (MinIO en local, Cloudflare R2 en prod) |
| IA | OpenAI (LLM + embeddings), Tavily (recherche web), Playwright (crawling) |
| Ops | Docker Compose · GitHub Actions · Railway · Sentry |

## Prérequis

- Docker Desktop
- [uv](https://docs.astral.sh/uv/) (Python)
- Node.js 20+

## Démarrage rapide

```bash
cp .env.example .env                 # puis renseigner SECRET_KEY et les clés API
docker compose up -d                 # postgres, redis, minio, api, worker, beat, frontend

# Backend (développement local hors Docker)
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.cli create-user --email vous@exemple.com --password '…'
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

API : `http://localhost:8000/api/docs`

## Tests

```bash
cd backend && uv run pytest -q       # aucun appel réseau : tous les services externes sont simulés
cd frontend && npm test
```

## Documentation

| Fichier | Contenu |
|---|---|
| [docs/01-cahier-des-charges.pdf](docs/01-cahier-des-charges.pdf) | Besoins, modules, règles métier |
| [docs/02-architecture-fonctionnelle.pdf](docs/02-architecture-fonctionnelle.pdf) | Domaines fonctionnels, flux, états |
| [docs/03-architecture-technique.pdf](docs/03-architecture-technique.pdf) | Composants, stack, déploiement |
| [docs/04-architecture-ia.md](docs/04-architecture-ia.md) | Pipelines IA, prompts, garde-fous |
| [docs/05-modele-donnees.md](docs/05-modele-donnees.md) | Tables, relations, énumérations |
| [docs/06-api-specification.md](docs/06-api-specification.md) | Conventions et routes de l'API |
| [docs/phases-de-developpement.md](docs/phases-de-developpement.md) | Les 13 phases en une page |
| [docs/superpowers/plans/2026-09-11-plan-developpement-complet.md](docs/superpowers/plans/2026-09-11-plan-developpement-complet.md) | Plan détaillé tâche par tâche |

## Structure

```
backend/          FastAPI, modèles, services, workers Celery, connecteurs, IA
frontend/         Next.js (App Router)
infrastructure/   Dockerfiles, init PostgreSQL, scripts de sauvegarde
docs/             Spécifications et plans
```
