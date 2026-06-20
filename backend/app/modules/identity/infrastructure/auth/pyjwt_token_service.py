"""Implementation of :class:`ITokenService` on top of PyJWT.

Access JWTs embed the user's effective permissions so endpoint dependencies
can authorise without a DB round-trip. Refresh JWTs carry only the user
public id and a ``jti`` that maps to the persisted ``refresh_tokens`` row.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from app.config import settings
from app.modules.identity.application.ports import (
    AccessTokenClaims,
    IssuedAccessToken,
    IssuedRefreshToken,
    ITokenService,
    RefreshTokenClaims,
)
from app.modules.identity.domain.refresh_token import (
    RefreshToken,
    RefreshTokenId,
    TokenStatus,
)
from app.modules.identity.domain.user import User

_ACCESS_TYPE = "access"
_REFRESH_TYPE = "refresh"


class PyJWTTokenService(ITokenService):
    """Issue/decode access + refresh JWTs.

    The secret comes from ``settings.SECRET_KEY`` and the algorithm from
    ``settings.ALGORITHM`` (HS256 by default).
    """

    def __init__(
        self,
        *,
        secret_key: str | None = None,
        algorithm: str | None = None,
        access_minutes: int | None = None,
        refresh_days: int | None = None,
    ) -> None:
        self._secret = secret_key or settings.SECRET_KEY
        self._algo = algorithm or settings.ALGORITHM
        self._access_ttl = timedelta(minutes=access_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self._refresh_ttl = timedelta(days=refresh_days or settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # --- access -------------------------------------------------------------

    def issue_access(self, user: User) -> IssuedAccessToken:
        now = datetime.now(UTC)
        exp = now + self._access_ttl
        payload: dict[str, Any] = {
            "sub": str(user.id.value),
            "username": str(user.username),
            "permissions": sorted(p.code for p in user.effective_permissions()),
            "type": _ACCESS_TYPE,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": str(uuid4()),
        }
        encoded = jwt.encode(payload, self._secret, algorithm=self._algo)
        return IssuedAccessToken(
            jwt=encoded, expires_in_seconds=int(self._access_ttl.total_seconds())
        )

    def decode_access(self, jwt_str: str) -> AccessTokenClaims | None:
        payload = self._decode(jwt_str, expected_type=_ACCESS_TYPE)
        if payload is None:
            return None
        try:
            return AccessTokenClaims(
                user_public_id=UUID(str(payload["sub"])),
                username=str(payload.get("username", "")),
                permissions=tuple(str(p) for p in payload.get("permissions", [])),
                expires_at=int(payload["exp"]),
            )
        except (KeyError, ValueError):
            return None

    # --- refresh ------------------------------------------------------------

    def issue_refresh(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedRefreshToken:
        now = datetime.now(UTC)
        exp = now + self._refresh_ttl
        token_id = uuid4()
        payload: dict[str, Any] = {
            "sub": str(user.id.value),
            "type": _REFRESH_TYPE,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": str(token_id),
        }
        encoded = jwt.encode(payload, self._secret, algorithm=self._algo)
        record = RefreshToken(
            id=RefreshTokenId(token_id),
            user_id=user.id,
            token_hash=self.hash_token(encoded),
            expires_at=exp,
            status=TokenStatus.ACTIVE,
            issued_at=now,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return IssuedRefreshToken(jwt=encoded, record=record)

    def decode_refresh(self, jwt_str: str) -> RefreshTokenClaims | None:
        payload = self._decode(jwt_str, expected_type=_REFRESH_TYPE)
        if payload is None:
            return None
        try:
            return RefreshTokenClaims(
                user_public_id=UUID(str(payload["sub"])),
                token_public_id=UUID(str(payload["jti"])),
                expires_at=int(payload["exp"]),
            )
        except (KeyError, ValueError):
            return None

    # --- helpers ------------------------------------------------------------

    @staticmethod
    def hash_token(jwt_str: str) -> str:
        return hashlib.sha256(jwt_str.encode("utf-8")).hexdigest()

    def _decode(self, jwt_str: str, *, expected_type: str) -> dict[str, Any] | None:
        if not jwt_str:
            return None
        try:
            payload = jwt.decode(
                jwt_str,
                self._secret,
                algorithms=[self._algo],
                options={"require": ["exp", "sub", "jti", "type"]},
            )
        except jwt.PyJWTError:
            return None
        if payload.get("type") != expected_type:
            return None
        return payload
