"""Domain events emitted by the identity aggregates.

Events are framework-agnostic dataclasses. The application layer publishes
them to the event bus after the UoW commits successfully.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRegistered(DomainEvent):
    user_id: UUID
    username: str
    email: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserBlocked(DomainEvent):
    user_id: UUID
    blocked_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UserUnblocked(DomainEvent):
    user_id: UUID
    unblocked_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRoleChanged(DomainEvent):
    user_id: UUID
    role_name: str
    granted: bool
    changed_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UserPermissionChanged(DomainEvent):
    user_id: UUID
    permission_code: str
    granted: bool
    changed_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshTokenIssued(DomainEvent):
    user_id: UUID
    token_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshTokenRotated(DomainEvent):
    user_id: UUID
    old_token_id: UUID
    new_token_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshTokenReuseDetected(DomainEvent):
    """Emitted when a rotated refresh token is presented again — likely theft."""

    user_id: UUID
    token_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UserLoggedOut(DomainEvent):
    user_id: UUID
    token_id: UUID | None = None
