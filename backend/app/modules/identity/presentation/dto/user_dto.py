"""User-facing response and request DTOs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.application.commands import UserSummary


class UserResponse(BaseModel):
    """Public projection of a user account."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Public UUID of the user")
    username: str
    email: str
    is_active: bool
    roles: list[str]
    permissions: list[str]

    @classmethod
    def from_summary(cls, summary: UserSummary) -> UserResponse:
        return cls(
            id=summary.public_id,
            username=summary.username,
            email=summary.email,
            is_active=summary.is_active,
            roles=list(summary.roles),
            permissions=list(summary.permissions),
        )


class AssignRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=50)


class GrantPermissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission: str = Field(min_length=1, max_length=100)
    granted: bool = Field(
        default=True,
        description=(
            "true => override grants the permission; "
            "false => override denies it (deny wins)."
        ),
    )


class SetStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocked: bool
