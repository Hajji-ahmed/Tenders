from fastapi import FastAPI

from app.api.router import api_router
from app.api.v1.auth import limiter
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env)
    # Swagger / OpenAPI uniquement en développement : en production, l'API est privée.
    expose_docs = settings.app_env == "dev"
    app = FastAPI(
        title="InnoSustain — Tenders API",
        version="0.1.0",
        docs_url="/api/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if expose_docs else None,
    )
    app.state.settings = settings
    app.state.limiter = limiter
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
