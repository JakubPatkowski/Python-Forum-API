"""User-facing endpoints: ``/api/v1/users/me`` and friends."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.container import get_identity_uow
from app.modules.identity.application.commands import UserSummary
from app.modules.identity.application.errors import UserNotFound
from app.modules.identity.application.ports import IIdentityUnitOfWork
from app.modules.identity.domain.user import UserId

from app.modules.identity.presentation.deps import CurrentUser
from app.modules.identity.presentation.dto.user_dto import UserResponse


router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user's profile",
)
async def me(
    user: CurrentUser,
    uow: Annotated[IIdentityUnitOfWork, Depends(get_identity_uow)],
) -> UserResponse:
    async with uow as session:
        domain_user = await session.users.get(UserId(user.public_id))
        if domain_user is None:
            raise UserNotFound(str(user.public_id))
        return UserResponse.from_summary(
            UserSummary(
                public_id=domain_user.id.value,
                username=str(domain_user.username),
                email=str(domain_user.email),
                is_active=domain_user.is_active,
                roles=tuple(r.name for r in domain_user.roles),
                permissions=tuple(p.code for p in domain_user.effective_permissions()),
            )
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a user's public profile by UUID",
)
async def get_user(
    user_id: str,
    uow: Annotated[IIdentityUnitOfWork, Depends(get_identity_uow)],
) -> UserResponse:
    from uuid import UUID  # local to avoid polluting module namespace

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user id",
        ) from exc

    async with uow as session:
        domain_user = await session.users.get(UserId(uid))
        if domain_user is None:
            raise UserNotFound(str(uid))
        return UserResponse.from_summary(
            UserSummary(
                public_id=domain_user.id.value,
                username=str(domain_user.username),
                email=str(domain_user.email),
                is_active=domain_user.is_active,
                roles=tuple(r.name for r in domain_user.roles),
                permissions=tuple(p.code for p in domain_user.effective_permissions()),
            )
        )
