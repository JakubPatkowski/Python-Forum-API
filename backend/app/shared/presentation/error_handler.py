"""Global FastAPI exception handlers.

Maps `DomainError` subclasses to HTTP responses with a uniform envelope,
and catches uncaught exceptions to avoid leaking stack traces.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.shared.domain.errors import DomainError
from app.shared.presentation.api_response import ErrorDetail, ErrorResponse

logger = structlog.get_logger(__name__)


def _envelope(
    *,
    code: str,
    message: str,
    field: str | None,
    request: Request,
    http_status: int,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, field=field),
        request_id=request.headers.get("X-Request-ID"),
    )
    return JSONResponse(status_code=http_status, content=body.model_dump(mode="json"))


async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return _envelope(
        code=exc.code,
        message=exc.message,
        field=exc.field,
        request=request,
        http_status=exc.http_status,
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Take the first validation error to keep envelope simple.
    first = exc.errors()[0] if exc.errors() else None
    field = ".".join(str(p) for p in first["loc"][1:]) if first else None
    message = first["msg"] if first else "Validation failed"
    return _envelope(
        code="VALIDATION_ERROR",
        message=message,
        field=field,
        request=request,
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", path=request.url.path)
    return _envelope(
        code="INTERNAL_ERROR",
        message="Internal server error",
        field=None,
        request=request,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all handlers to the FastAPI app."""
    app.add_exception_handler(DomainError, _handle_domain_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unexpected)
