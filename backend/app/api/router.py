from fastapi import APIRouter

from app.api.v1 import auth, company, documents, health, jobs

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(company.router)
api_router.include_router(documents.router)
