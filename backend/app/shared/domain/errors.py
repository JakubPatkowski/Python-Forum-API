"""Domain error hierarchy.

These exceptions are framework-agnostic — they can be raised from any
domain or application code. The presentation layer maps them to HTTP
status codes in `shared.presentation.error_handler`.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for all domain-layer errors.

    Subclasses are mapped to HTTP responses by the presentation layer.
    Each subclass has a stable `code` used in error response envelopes.
    """

    code: str = "DOMAIN_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class NotFoundError(DomainError):
    """The requested resource does not exist."""

    code = "NOT_FOUND"
    http_status = 404


class ConflictError(DomainError):
    """The request conflicts with current resource state (duplicate key, ...)."""

    code = "CONFLICT"
    http_status = 409


class ValidationError(DomainError):
    """A domain invariant was violated (e.g. invalid email format)."""

    code = "VALIDATION_ERROR"
    http_status = 422


class PermissionDeniedError(DomainError):
    """The caller is not authorized to perform this action."""

    code = "PERMISSION_DENIED"
    http_status = 403


class UnauthenticatedError(DomainError):
    """The caller did not present valid credentials."""

    code = "UNAUTHENTICATED"
    http_status = 401
