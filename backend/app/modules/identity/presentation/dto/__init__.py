"""Pydantic request/response models exposed by the identity API."""

from app.modules.identity.presentation.dto.auth_dto import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.modules.identity.presentation.dto.user_dto import (
    AssignRoleRequest,
    GrantPermissionRequest,
    SetStatusRequest,
    UserResponse,
)

__all__ = [
    "AssignRoleRequest",
    "GrantPermissionRequest",
    "LoginRequest",
    "RegisterRequest",
    "SetStatusRequest",
    "TokenResponse",
    "UserResponse",
]
