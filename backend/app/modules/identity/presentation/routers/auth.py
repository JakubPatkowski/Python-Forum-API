"""Authentication endpoints: register / login / refresh / logout.

The refresh token is delivered both in the JSON body (for non-browser clients)
and as an ``httpOnly Secure SameSite=Lax`` cookie so a browser frontend never
exposes it to JavaScript.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.container import (
    get_login_uc,
    get_logout_all_uc,
    get_logout_uc,
    get_refresh_uc,
    get_register_user_uc,
)
from app.modules.identity.application.commands import (
    LogoutAllCommand,
    LogoutCommand,
    RefreshSessionCommand,
)
from app.modules.identity.application.use_cases import (
    LoginUseCase,
    LogoutAllUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterUserUseCase,
)
from app.modules.identity.presentation.deps import (
    CurrentUser,
    client_ip,
    user_agent,
)
from app.modules.identity.presentation.dto.auth_dto import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.modules.identity.presentation.dto.user_dto import UserResponse
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError

router = APIRouter()


def _raise_if_error(result: object) -> None:
    if isinstance(result, Err):
        # ``DomainError`` is handled by the global handler; re-raise as-is.
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
async def register(
    body: RegisterRequest,
    uc: Annotated[RegisterUserUseCase, Depends(get_register_user_uc)],
) -> UserResponse:
    result = await uc.execute(body.to_command())
    _raise_if_error(result)
    return UserResponse.from_summary(result.value)  # type: ignore[union-attr]


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with username/email + password",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    uc: Annotated[LoginUseCase, Depends(get_login_uc)],
) -> TokenResponse:
    cmd = body.to_command(
        user_agent=user_agent(request), ip_address=client_ip(request)
    )
    result = await uc.execute(cmd)
    _raise_if_error(result)
    pair = result.value  # type: ignore[union-attr]
    _set_refresh_cookie(response, pair.refresh_token)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a refresh token into a new access+refresh pair",
)
async def refresh(
    request: Request,
    response: Response,
    uc: Annotated[RefreshSessionUseCase, Depends(get_refresh_uc)],
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    # Prefer cookie (browser) but allow a JSON body with ``refresh_token`` for
    # non-browser clients.
    token = refresh_cookie
    if token is None:
        try:
            body = await request.json()
        except Exception:
            body = None
        if isinstance(body, dict):
            token = body.get("refresh_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing"
        )
    cmd = RefreshSessionCommand(
        refresh_token=token,
        user_agent=user_agent(request),
        ip_address=client_ip(request),
    )
    result = await uc.execute(cmd)
    if isinstance(result, Err):
        _clear_refresh_cookie(response)
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))
    pair = result.value
    _set_refresh_cookie(response, pair.refresh_token)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    response: Response,
    user: CurrentUser,
    uc: Annotated[LogoutUseCase, Depends(get_logout_uc)],
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.REFRESH_COOKIE_NAME)] = None,
) -> Response:
    await uc.execute(
        LogoutCommand(refresh_token=refresh_cookie, user_public_id=user.public_id)
    )
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke every refresh token of the current user",
)
async def logout_all(
    response: Response,
    user: CurrentUser,
    uc: Annotated[LogoutAllUseCase, Depends(get_logout_all_uc)],
) -> Response:
    result = await uc.execute(LogoutAllCommand(user_public_id=user.public_id))
    _raise_if_error(result)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
