"""RefreshToken entity — whitelist record of an issued refresh JWT.

A refresh token is *active* when first issued, becomes *rotated* when used
to mint a new pair (rotation), and *revoked* on logout or reuse detection.
The ``token_hash`` is ``sha256(raw_jwt)`` so a leaked DB does not give an
attacker usable JWTs — they still need the secret to forge new ones, and
re-presenting a rotated token triggers reuse-detection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from app.shared.domain.entity import Entity
from app.shared.domain.entity_id import EntityId

from app.modules.identity.domain.user import UserId


class RefreshTokenId(EntityId["RefreshToken"]):
    """Public id of a refresh token; carried as ``jti`` inside the JWT."""


class TokenStatus(StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"


class RefreshToken(Entity[RefreshTokenId]):
    """A persisted refresh token record."""

    def __init__(
        self,
        *,
        id: RefreshTokenId,
        user_id: UserId,
        token_hash: str,
        expires_at: datetime,
        status: TokenStatus = TokenStatus.ACTIVE,
        issued_at: datetime | None = None,
        revoked_at: datetime | None = None,
        replaced_by_id: RefreshTokenId | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.token_hash = token_hash
        self.expires_at = expires_at
        self.status = status
        self.issued_at = issued_at or datetime.now(UTC)
        self.revoked_at = revoked_at
        self.replaced_by_id = replaced_by_id
        self.user_agent = user_agent
        self.ip_address = ip_address

    # --- queries ------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self._aware(self.expires_at)

    @property
    def is_active(self) -> bool:
        return self.status == TokenStatus.ACTIVE and not self.is_expired

    @property
    def is_rotated(self) -> bool:
        return self.status == TokenStatus.ROTATED

    # --- mutations ----------------------------------------------------------

    def rotate_to(self, new_token: "RefreshToken") -> None:
        """Mark this token as rotated and link to its replacement."""
        self.status = TokenStatus.ROTATED
        self.revoked_at = datetime.now(UTC)
        self.replaced_by_id = new_token.id

    def revoke(self) -> None:
        """Manually revoke the token (logout or admin action)."""
        if self.status == TokenStatus.REVOKED:
            return
        self.status = TokenStatus.REVOKED
        self.revoked_at = datetime.now(UTC)

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        """Some DB drivers return naive datetimes; treat them as UTC."""
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
