from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

COOKIE_NAME = "access_token"


class AppError(Exception):
    """Erreur métier renvoyée au client sous la forme {"error": {"code", "message"}}."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str = "", *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message or self.code
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ValidationError(AppError):
    """Entrée métier invalide (type de fichier, valeur hors plage…). À lever explicitement —
    les ValueError génériques restent des 500 journalisées."""

    status_code = 422
    code = "validation_error"


class ForbiddenTransition(AppError):
    status_code = 422
    code = "invalid_transition"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


def _error_response(status_code: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message, **extra}}
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        response = _error_response(exc.status_code, exc.code, exc.message)
        if exc.status_code == 401:
            # Un cookie présent mais rejeté ferait boucler le client entre /login et /dashboard.
            response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"{loc} : {first.get('msg', 'valeur invalide')}" if loc else "Requête invalide"
        details = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in errors]
        return _error_response(422, "validation_error", message, details=details)

    @app.exception_handler(RateLimitExceeded)
    async def _handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return _error_response(429, "rate_limited", f"Trop de tentatives, réessayez plus tard ({exc.detail})")
