"""Dependency-Injection container for the application.

Each ``get_*`` callable here is consumed by FastAPI through
``Annotated[..., Depends(get_*)]``. Stateless singletons (event bus, hasher,
token service) are cached with ``functools.lru_cache``; per-request
objects (UoW, use cases) are not, so each request gets a fresh session.
"""

from __future__ import annotations

from functools import lru_cache

from app.shared.application.event_bus import IEventBus
from app.shared.infrastructure.db import SessionLocal
from app.shared.infrastructure.eventbus import InMemoryEventBus

from app.modules.identity.application.ports import (
    IIdentityUnitOfWork,
    IPasswordHasher,
    ITokenService,
)
from app.modules.identity.application.use_cases import (
    AssignRoleUseCase,
    DenyPermissionUseCase,
    GrantPermissionUseCase,
    LoginUseCase,
    LogoutAllUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterUserUseCase,
    RevokeRoleUseCase,
    SetUserStatusUseCase,
)
from app.modules.identity.infrastructure.auth import (
    Argon2Hasher,
    PyJWTTokenService,
)
from app.modules.identity.infrastructure.unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)


# --------------------------------------------------------------------------- #
# Singletons                                                                  #
# --------------------------------------------------------------------------- #


@lru_cache
def get_event_bus() -> IEventBus:
    """In-memory bus until phase 4 swaps in RabbitMQ."""
    return InMemoryEventBus()


@lru_cache
def get_password_hasher() -> IPasswordHasher:
    return Argon2Hasher()


@lru_cache
def get_token_service() -> ITokenService:
    return PyJWTTokenService()


# --------------------------------------------------------------------------- #
# Per-request                                                                 #
# --------------------------------------------------------------------------- #


def get_identity_uow() -> IIdentityUnitOfWork:
    """A fresh UoW per FastAPI request. Caller must ``async with`` it."""
    return SqlAlchemyIdentityUnitOfWork(SessionLocal)


# --------------------------------------------------------------------------- #
# Use case providers                                                          #
# --------------------------------------------------------------------------- #


def get_register_user_uc() -> RegisterUserUseCase:
    return RegisterUserUseCase(
        uow=get_identity_uow(),
        hasher=get_password_hasher(),
        bus=get_event_bus(),
    )


def get_login_uc() -> LoginUseCase:
    return LoginUseCase(
        uow=get_identity_uow(),
        hasher=get_password_hasher(),
        tokens=get_token_service(),
        bus=get_event_bus(),
    )


def get_refresh_uc() -> RefreshSessionUseCase:
    return RefreshSessionUseCase(
        uow=get_identity_uow(),
        tokens=get_token_service(),
        bus=get_event_bus(),
    )


def get_logout_uc() -> LogoutUseCase:
    return LogoutUseCase(
        uow=get_identity_uow(),
        tokens=get_token_service(),
        bus=get_event_bus(),
    )


def get_logout_all_uc() -> LogoutAllUseCase:
    return LogoutAllUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_assign_role_uc() -> AssignRoleUseCase:
    return AssignRoleUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_revoke_role_uc() -> RevokeRoleUseCase:
    return RevokeRoleUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_grant_permission_uc() -> GrantPermissionUseCase:
    return GrantPermissionUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_deny_permission_uc() -> DenyPermissionUseCase:
    return DenyPermissionUseCase(uow=get_identity_uow(), bus=get_event_bus())


def get_set_user_status_uc() -> SetUserStatusUseCase:
    return SetUserStatusUseCase(uow=get_identity_uow(), bus=get_event_bus())
