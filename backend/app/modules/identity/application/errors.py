"""Application-level errors specific to the identity module.

These map to HTTP 4xx through the global handler in
``shared.presentation.error_handler``.
"""

from __future__ import annotations

from app.shared.domain.errors import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    UnauthenticatedError,
)


class UsernameAlreadyTaken(ConflictError):
    code = "USERNAME_TAKEN"

    def __init__(self, username: str) -> None:
        super().__init__(f"Username '{username}' is already taken", field="username")


class EmailAlreadyTaken(ConflictError):
    code = "EMAIL_TAKEN"

    def __init__(self, email: str) -> None:
        super().__init__(f"Email '{email}' is already registered", field="email")


class InvalidCredentials(UnauthenticatedError):
    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Invalid username or password")


class UserBlocked(PermissionDeniedError):
    code = "USER_BLOCKED"

    def __init__(self) -> None:
        super().__init__("User account is blocked")


class InvalidRefreshToken(UnauthenticatedError):
    code = "INVALID_REFRESH_TOKEN"

    def __init__(self, message: str = "Invalid refresh token") -> None:
        super().__init__(message)


class RefreshTokenReuseDetected(UnauthenticatedError):
    """Raised when a rotated refresh token is presented again."""

    code = "REFRESH_TOKEN_REUSE"

    def __init__(self) -> None:
        super().__init__("Refresh token has already been used; sessions revoked")


class UserNotFound(NotFoundError):
    code = "USER_NOT_FOUND"

    def __init__(self, identifier: str) -> None:
        super().__init__(f"User {identifier!r} not found")


class RoleNotFound(NotFoundError):
    code = "ROLE_NOT_FOUND"

    def __init__(self, name: str) -> None:
        super().__init__(f"Role {name!r} not found")


class PermissionNotFound(NotFoundError):
    code = "PERMISSION_NOT_FOUND"

    def __init__(self, code_: str) -> None:
        super().__init__(f"Permission {code_!r} not found")


IdentityError = DomainError
"""Convenience alias — every identity-app error is a :class:`DomainError`."""
