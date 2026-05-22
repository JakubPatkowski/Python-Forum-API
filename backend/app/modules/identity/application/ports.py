"""Ports (interfaces) consumed by identity use cases.

Implementations live in ``modules.identity.infrastructure``. Defining them
here keeps the application layer decoupled from SQLAlchemy / PyJWT / Argon2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Self
from types import TracebackType
from uuid import UUID

from app.shared.application.repository import IRepository

from app.modules.identity.domain.refresh_token import (
    RefreshToken,
    RefreshTokenId,
)
from app.modules.identity.domain.role import Role
from app.modules.identity.domain.user import User, UserId
from app.modules.identity.domain.value_objects import Email, Username


# --------------------------------------------------------------------------- #
# Repositories                                                                #
# --------------------------------------------------------------------------- #


class IUserRepository(IRepository[User, UserId], Protocol):
    """Persistence port for :class:`User` aggregates."""

    async def get_by_username(self, username: Username) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def get_by_username_or_email(self, value: str) -> User | None: ...


class IRoleRepository(Protocol):
    async def get_by_name(self, name: str) -> Role | None: ...

    async def list_all(self) -> list[Role]: ...


class IRefreshTokenRepository(
    IRepository[RefreshToken, RefreshTokenId], Protocol
):
    async def get_by_public_id(self, public_id: UUID) -> RefreshToken | None: ...

    async def save(self, token: RefreshToken) -> None:
        """Persist mutations on an already-loaded refresh token (status, replaced_by)."""

    async def revoke_chain_from(self, token_id: RefreshTokenId) -> None:
        """Revoke the token and the whole rotation chain (descendants)."""

    async def revoke_all_for_user(self, user_id: UserId) -> None: ...


# --------------------------------------------------------------------------- #
# Unit of Work                                                                #
# --------------------------------------------------------------------------- #


class IIdentityUnitOfWork(Protocol):
    """Transactional scope grouping identity repositories."""

    users: IUserRepository
    roles: IRoleRepository
    refresh_tokens: IRefreshTokenRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


# --------------------------------------------------------------------------- #
# Cryptography & tokens                                                       #
# --------------------------------------------------------------------------- #


class IPasswordHasher(Protocol):
    """Strategy port for password hashing.

    Implementations: Argon2 (production), a deterministic fake for tests.
    """

    def hash(self, plain: str) -> str: ...

    def verify(self, hashed: str, plain: str) -> bool: ...

    def needs_rehash(self, hashed: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    """A freshly-minted access JWT plus its metadata."""

    jwt: str
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class IssuedRefreshToken:
    """A freshly-minted refresh JWT and the persistence record it maps to."""

    jwt: str
    record: RefreshToken


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Decoded claims of an access token."""

    user_public_id: UUID
    username: str
    permissions: tuple[str, ...]
    expires_at: int  # epoch seconds


@dataclass(frozen=True, slots=True)
class RefreshTokenClaims:
    """Decoded claims of a refresh token."""

    user_public_id: UUID
    token_public_id: UUID
    expires_at: int


class ITokenService(Protocol):
    """JWT issuer/decoder for access + refresh tokens."""

    def issue_access(self, user: User) -> IssuedAccessToken: ...

    def issue_refresh(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedRefreshToken: ...

    def decode_access(self, jwt: str) -> AccessTokenClaims | None: ...

    def decode_refresh(self, jwt: str) -> RefreshTokenClaims | None: ...

    @staticmethod
    def hash_token(jwt: str) -> str: ...
