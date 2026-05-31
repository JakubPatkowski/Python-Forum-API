"""Presentation dependencies specific to the files module.

``OptionalCurrentUser`` resolves the caller if a valid bearer token is present,
otherwise yields ``None`` — used by public read endpoints that still want to
recognise the uploader (so they can see their own not-yet-attached files).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import get_token_service
from app.modules.identity.application.ports import ITokenService
from app.modules.identity.presentation.deps import CurrentUserData

_bearer = HTTPBearer(auto_error=False)


def optional_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    tokens: Annotated[ITokenService, Depends(get_token_service)],
) -> CurrentUserData | None:
    if creds is None or not creds.credentials:
        return None
    claims = tokens.decode_access(creds.credentials)
    if claims is None:
        return None
    return CurrentUserData(
        public_id=claims.user_public_id,
        username=claims.username,
        permissions=frozenset(claims.permissions),
    )


OptionalCurrentUser = Annotated[CurrentUserData | None, Depends(optional_current_user)]
