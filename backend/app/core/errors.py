from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


class ForbiddenTransition(AppError):
    status_code = 422
    code = "invalid_transition"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": {"code": "validation_error", "message": str(exc)}}
        )
