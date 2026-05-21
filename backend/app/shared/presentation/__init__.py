"""Shared presentation-layer helpers (envelopes, error handler, deps)."""

from app.shared.presentation.api_response import (
    ApiResponse,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
)
from app.shared.presentation.deps import DbSession
from app.shared.presentation.error_handler import register_exception_handlers

__all__ = [
    "ApiResponse",
    "DbSession",
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedResponse",
    "register_exception_handlers",
]
