"""Command and query DTOs consumed by identity use cases.

These are plain dataclasses on purpose: they belong to the application layer
and must not depend on FastAPI or Pydantic. The presentation layer's Pydantic
request bodies map *to* these commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    username: str
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class LoginCommand:
    username_or_email: str
    password: str
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshSessionCommand:
    refresh_token: str
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    refresh_token: str | None
    user_public_id: UUID


@dataclass(frozen=True, slots=True)
class LogoutAllCommand:
    user_public_id: UUID


@dataclass(frozen=True, slots=True)
class AssignRoleCommand:
    target_user_public_id: UUID
    role_name: str
    by_user_public_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RevokeRoleCommand:
    target_user_public_id: UUID
    role_name: str
    by_user_public_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class GrantPermissionCommand:
    target_user_public_id: UUID
    permission_code: str
    by_user_public_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DenyPermissionCommand:
    target_user_public_id: UUID
    permission_code: str
    by_user_public_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SetUserStatusCommand:
    target_user_public_id: UUID
    blocked: bool
    by_user_public_id: UUID | None = None


# --------------------------------------------------------------------------- #
# Outputs of use cases                                                        #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Pair of tokens returned by login / refresh."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds — access token TTL


@dataclass(frozen=True, slots=True)
class UserSummary:
    """Lightweight projection returned by use cases to the presentation layer."""

    public_id: UUID
    username: str
    email: str
    is_active: bool
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
