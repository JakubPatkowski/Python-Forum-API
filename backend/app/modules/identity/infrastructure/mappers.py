"""Mappers between identity ORM rows and domain aggregates.

The repository layer calls these to convert a fully-loaded ORM graph into
an aggregate, and the other way around when persisting.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.refresh_token import (
    RefreshToken,
    RefreshTokenId,
    TokenStatus,
)
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.domain.user import User, UserId, UserStatus
from app.modules.identity.domain.value_objects import Email, Username
from app.modules.identity.infrastructure.orm import (
    RefreshTokenOrm,
    RoleOrm,
    UserOrm,
)

# Map status enum values between domain and DB. Both happen to share the
# same strings; keeping the table makes the boundary explicit.
_STATUS_TO_DB: Final[dict[UserStatus, str]] = {
    UserStatus.ACTIVE: "active",
    UserStatus.BLOCKED: "blocked",
    UserStatus.PENDING_VERIFICATION: "pending_verification",
}
_STATUS_FROM_DB: Final[dict[str, UserStatus]] = {v: k for k, v in _STATUS_TO_DB.items()}


def role_from_orm(row: RoleOrm, permission_codes: Iterable[str]) -> Role:
    return Role(
        id=RoleId(UUID(int=int(row.id))),  # phantom-typed; not exposed to API
        name=row.name,
        description=row.description,
        permissions={Permission(code) for code in permission_codes},
    )


def user_from_orm(
    row: UserOrm,
    *,
    roles: list[Role],
    granted_codes: Iterable[str],
    denied_codes: Iterable[str],
) -> User:
    """Build a domain :class:`User` from an ORM row and its related data."""
    status_value = row.status or "active"
    return User(
        id=UserId(row.public_id),
        username=Username(row.username),
        email=Email(row.email),
        password_hash=row.password_hash or row.hashed_password,
        status=_STATUS_FROM_DB.get(str(status_value), UserStatus.ACTIVE),
        roles=set(roles),
        granted_permissions={Permission(c) for c in granted_codes},
        denied_permissions={Permission(c) for c in denied_codes},
        avatar_file_id=row.avatar_file_id,
        created_at=_as_aware(row.created_at),
        updated_at=_as_aware(row.updated_at) if row.updated_at else None,
    )


def refresh_token_from_orm(
    row: RefreshTokenOrm, *, user_public_id: UUID
) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId(row.public_id),
        user_id=UserId(user_public_id),
        token_hash=row.token_hash,
        expires_at=_as_aware(row.expires_at),
        status=TokenStatus(row.status),
        issued_at=_as_aware(row.issued_at),
        revoked_at=_as_aware(row.revoked_at) if row.revoked_at else None,
        replaced_by_id=None,  # internal FK only — not surfaced to domain users
        user_agent=row.user_agent,
        ip_address=str(row.ip_address) if row.ip_address else None,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _as_aware(dt: datetime) -> datetime:
    """Treat naive timestamps coming from psycopg as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def status_to_db(status: UserStatus) -> str:
    return _STATUS_TO_DB[status]


def role_orm_id_to_int(role_id: RoleId) -> int:
    """Recover the integer DB id from a phantom-typed :class:`RoleId`.

    Roles are seeded with deterministic small ids (1..N) and we wrap them
    in a UUID with ``UUID(int=...)`` for type safety. This helper reverses
    the encoding.
    """
    return int(role_id.value)
