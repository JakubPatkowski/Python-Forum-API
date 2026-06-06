"""Admin operations on users: list, block/unblock, role and permission edits.

All endpoints require an authenticated user with the matching ``user.*`` /
``role.manage`` permission.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import (
    get_assign_role_uc,
    get_deny_permission_uc,
    get_grant_permission_uc,
    get_revoke_role_uc,
    get_set_user_status_uc,
)
from app.modules.identity.application.commands import (
    AssignRoleCommand,
    DenyPermissionCommand,
    GrantPermissionCommand,
    RevokeRoleCommand,
    SetUserStatusCommand,
    UserSummary,
)
from app.modules.identity.application.use_cases import (
    AssignRoleUseCase,
    DenyPermissionUseCase,
    GrantPermissionUseCase,
    RevokeRoleUseCase,
    SetUserStatusUseCase,
)
from app.modules.identity.infrastructure.orm import UserOrm
from app.modules.identity.presentation.deps import requires
from app.modules.identity.presentation.dto.user_dto import (
    AssignRoleRequest,
    GrantPermissionRequest,
    SetStatusRequest,
    UserResponse,
)
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError
from app.shared.presentation.deps import DbSession

router = APIRouter()


def _raise_if_error(result: object) -> None:
    if isinstance(result, Err):
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


# --------------------------------------------------------------------------- #
# Read endpoints                                                              #
# --------------------------------------------------------------------------- #


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List users (admins / moderators)",
    dependencies=[Depends(requires("user.read.any"))],
)
async def list_users(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    """Lightweight projection — phase-6 will turn this into a cursor-paginated view."""
    rows = (
        db.execute(select(UserOrm).order_by(UserOrm.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return [_row_to_response(db, r) for r in rows]


# --------------------------------------------------------------------------- #
# Write endpoints                                                             #
# --------------------------------------------------------------------------- #


@router.post(
    "/{user_id}/roles",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign a role to a user",
    dependencies=[Depends(requires("role.manage"))],
)
async def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    user: Annotated[object, Depends(requires("role.manage"))],
    uc: Annotated[AssignRoleUseCase, Depends(get_assign_role_uc)],
) -> None:
    result = await uc.execute(
        AssignRoleCommand(
            target_user_public_id=user_id,
            role_name=body.role,
            by_user_public_id=getattr(user, "public_id", None),
        )
    )
    _raise_if_error(result)


@router.delete(
    "/{user_id}/roles/{role_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a role from a user",
    dependencies=[Depends(requires("role.manage"))],
)
async def revoke_role(
    user_id: UUID,
    role_name: str,
    user: Annotated[object, Depends(requires("role.manage"))],
    uc: Annotated[RevokeRoleUseCase, Depends(get_revoke_role_uc)],
) -> None:
    result = await uc.execute(
        RevokeRoleCommand(
            target_user_public_id=user_id,
            role_name=role_name,
            by_user_public_id=getattr(user, "public_id", None),
        )
    )
    _raise_if_error(result)


@router.post(
    "/{user_id}/permissions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Grant or deny a per-user permission override",
    dependencies=[Depends(requires("role.manage"))],
)
async def set_permission_override(
    user_id: UUID,
    body: GrantPermissionRequest,
    user: Annotated[object, Depends(requires("role.manage"))],
    grant_uc: Annotated[GrantPermissionUseCase, Depends(get_grant_permission_uc)],
    deny_uc: Annotated[DenyPermissionUseCase, Depends(get_deny_permission_uc)],
) -> None:
    actor = getattr(user, "public_id", None)
    if body.granted:
        result = await grant_uc.execute(
            GrantPermissionCommand(
                target_user_public_id=user_id,
                permission_code=body.permission,
                by_user_public_id=actor,
            )
        )
    else:
        result = await deny_uc.execute(
            DenyPermissionCommand(
                target_user_public_id=user_id,
                permission_code=body.permission,
                by_user_public_id=actor,
            )
        )
    _raise_if_error(result)


@router.patch(
    "/{user_id}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Block or unblock a user account",
    dependencies=[Depends(requires("user.manage"))],
)
async def set_status(
    user_id: UUID,
    body: SetStatusRequest,
    user: Annotated[object, Depends(requires("user.manage"))],
    uc: Annotated[SetUserStatusUseCase, Depends(get_set_user_status_uc)],
) -> None:
    result = await uc.execute(
        SetUserStatusCommand(
            target_user_public_id=user_id,
            blocked=body.blocked,
            by_user_public_id=getattr(user, "public_id", None),
        )
    )
    _raise_if_error(result)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _row_to_response(db: Session, row: UserOrm) -> UserResponse:
    """Build a response from a raw ORM row.

    Reuses the per-row effective permission lookup via the view planned for
    phase 6; until then we re-hydrate through the user repository.
    """
    from app.modules.identity.infrastructure.repositories.user_repo import (
        SqlAlchemyUserRepository,
    )

    repo = SqlAlchemyUserRepository(db)
    # We deliberately call internal helpers here for cheap projection.
    roles = repo._load_user_roles(row.id)
    granted, denied = repo._load_user_overrides(row.id)
    perms: set[str] = set()
    for r in roles:
        perms.update(p.code for p in r.permissions)
    perms.update(granted)
    perms.difference_update(denied)
    return UserResponse.from_summary(
        UserSummary(
            public_id=row.public_id,
            username=row.username,
            email=row.email,
            is_active=(row.status or "active") == "active",
            roles=tuple(r.name for r in roles),
            permissions=tuple(sorted(perms)),
        )
    )
