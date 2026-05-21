"""Zależności do autoryzacji opartej na rolach (RBAC)."""
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models.user import User, UserRole

# Hierarchia ról — większa liczba = więcej uprawnień
_ROLE_RANK: dict[UserRole, int] = {
    UserRole.USER: 1,
    UserRole.MODERATOR: 2,
    UserRole.ADMIN: 3,
}


def has_role(user: User, minimum: UserRole) -> bool:
    """Czy user ma rolę >= `minimum` w hierarchii."""
    return _ROLE_RANK[UserRole(user.role)] >= _ROLE_RANK[minimum]


def require_role(minimum: UserRole) -> Callable[..., User]:
    """Fabryka dependency: wymaga roli >= `minimum`."""

    def _dep(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if not has_role(current_user, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Wymagana rola {minimum.value} lub wyższa",
            )
        return current_user

    return _dep


# Gotowe zależności do użycia w routerach
require_user = require_role(UserRole.USER)
require_moderator = require_role(UserRole.MODERATOR)
require_admin = require_role(UserRole.ADMIN)
