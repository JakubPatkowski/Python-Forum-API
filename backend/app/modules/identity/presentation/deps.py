"""FastAPI dependencies for authentication and authorisation.

``CurrentUser`` is the type used by routes that need an authenticated caller.
``requires(*codes)`` builds a dependency that checks the JWT's permission
claims for any of the listed codes.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import get_token_service
from app.modules.identity.application.ports import (
    AccessTokenClaims,
    ITokenService,
)

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUserData:
    """What ``get_current_user`` returns to a router.

    Holds the parsed JWT claims — no DB hit on the auth path.
    """

    public_id: UUID
    username: str
    permissions: frozenset[str]

    def has(self, code: str) -> bool:
        return code in self.permissions

    def has_any(self, *codes: str) -> bool:
        return any(c in self.permissions for c in codes)


def _credentials(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return creds.credentials


def get_current_user(
    jwt_str: Annotated[str, Depends(_credentials)],
    tokens: Annotated[ITokenService, Depends(get_token_service)],
) -> CurrentUserData:
    """Parse the bearer token and expose the caller's identity."""
    claims: AccessTokenClaims | None = tokens.decode_access(jwt_str)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUserData(
        public_id=claims.user_public_id,
        username=claims.username,
        permissions=frozenset(claims.permissions),
    )


CurrentUser = Annotated[CurrentUserData, Depends(get_current_user)]


def requires(*permission_codes: str) -> Callable[..., Coroutine[Any, Any, CurrentUserData]]:
    """Build a dependency that requires *any* of the listed permission codes."""

    async def _checker(
        user: Annotated[CurrentUserData, Depends(get_current_user)],
    ) -> CurrentUserData:
        if not user.has_any(*permission_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied (requires one of: {', '.join(permission_codes)})",
            )
        return user

    return _checker


def client_ip(request: Request) -> str | None:
    """Best-effort client IP, honouring ``X-Forwarded-For`` from the ingress."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")
