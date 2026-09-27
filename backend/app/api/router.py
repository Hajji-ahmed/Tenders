from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    applications,
    auth,
    company,
    documents,
    health,
    jobs,
    questions,
    requirements,
    scoring,
    search,
    search_profiles,
    searches,
    sources,
    templates,
    tender_documents,
    tenders,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(company.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)  # /search (recherche interne) ≠ /searches (lancements)
api_router.include_router(search_profiles.router)
api_router.include_router(sources.router)
api_router.include_router(searches.router)
api_router.include_router(scoring.router)  # avant `tenders` : /tenders/kanban ≠ /tenders/{tender_id}
api_router.include_router(tender_documents.router)
api_router.include_router(analysis.router)
api_router.include_router(requirements.router)
api_router.include_router(questions.router)
api_router.include_router(templates.router)
api_router.include_router(applications.router)
api_router.include_router(tenders.router)
