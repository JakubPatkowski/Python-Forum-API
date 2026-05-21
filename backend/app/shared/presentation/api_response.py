"""Public response envelopes used by all API endpoints.

Successful responses wrap their payload in `ApiResponse`. Errors are emitted
as `ErrorResponse` via the global exception handler. Listings use
`PaginatedResponse` with cursor-based pagination (see phase 6).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiResponse[T](BaseModel):
    """Envelope for successful responses."""

    model_config = ConfigDict(from_attributes=True)

    data: T
    meta: dict[str, str] | None = None


class ErrorDetail(BaseModel):
    """A single error returned from the API."""

    code: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="Human-readable description.")
    field: str | None = Field(
        default=None,
        description="Name of the offending input field, if applicable.",
    )


class ErrorResponse(BaseModel):
    """Envelope for failed responses."""

    error: ErrorDetail
    request_id: str | None = Field(
        default=None,
        description="Correlation id from X-Request-ID, when available.",
    )


class PaginatedResponse[T](BaseModel):
    """Envelope for keyset-paginated listings.

    `next_cursor` is opaque (base64-encoded JSON). Clients should pass it back
    verbatim in the next request. `null` means no more pages.
    """

    items: list[T]
    next_cursor: str | None = None
    total: int | None = Field(
        default=None,
        description="Optional total count — only set when cheap to compute.",
    )
