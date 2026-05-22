"""Identity use cases — each one orchestrates a single business intent."""

from app.modules.identity.application.use_cases.assign_role import (
    AssignRoleUseCase,
    RevokeRoleUseCase,
)
from app.modules.identity.application.use_cases.grant_permission import (
    DenyPermissionUseCase,
    GrantPermissionUseCase,
)
from app.modules.identity.application.use_cases.login import LoginUseCase
from app.modules.identity.application.use_cases.logout import (
    LogoutAllUseCase,
    LogoutUseCase,
)
from app.modules.identity.application.use_cases.refresh_session import (
    RefreshSessionUseCase,
)
from app.modules.identity.application.use_cases.register_user import (
    RegisterUserUseCase,
)
from app.modules.identity.application.use_cases.set_user_status import (
    SetUserStatusUseCase,
)

__all__ = [
    "AssignRoleUseCase",
    "DenyPermissionUseCase",
    "GrantPermissionUseCase",
    "LoginUseCase",
    "LogoutAllUseCase",
    "LogoutUseCase",
    "RefreshSessionUseCase",
    "RegisterUserUseCase",
    "RevokeRoleUseCase",
    "SetUserStatusUseCase",
]
