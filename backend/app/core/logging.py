import logging
import re
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
# Un X-Request-ID fourni par le client n'est repris que s'il est court et sans caractères spéciaux
# (il est injecté dans chaque ligne de log).
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _add_request_id(_logger, _method, event_dict):
    event_dict["request_id"] = request_id_var.get()
    return event_dict


def configure_logging(env: str) -> None:
    """Console lisible en dev, JSON ailleurs (agrégable par Railway / Sentry)."""
    renderer = structlog.dev.ConsoleRenderer() if env == "dev" else structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str):
    return structlog.get_logger(name)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propage ou génère un X-Request-ID, présent dans chaque log et chaque réponse."""

    async def dispatch(self, request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
