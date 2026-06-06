"""Request and response DTOs for the auth endpoints."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

from app.modules.identity.application.commands import (
    LoginCommand,
    RegisterUserCommand,
)


class RegisterRequest(BaseModel):
    """Body of ``POST /api/v1/auth/register``."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    def to_command(self) -> RegisterUserCommand:
        return RegisterUserCommand(
            username=self.username,
            email=str(self.email),
            password=self.password,
        )


class LoginRequest(BaseModel):
    """Body of ``POST /api/v1/auth/login``.

    Accepts either the username or the email in ``username_or_email``.
    """

    model_config = ConfigDict(extra="forbid")

    username_or_email: str = Field(
        validation_alias=AliasChoices("login", "username_or_email"),
        min_length=1,
        max_length=255,
    )
    password: str = Field(min_length=1, max_length=128)

    def to_command(
        self, *, user_agent: str | None, ip_address: str | None
    ) -> LoginCommand:
        return LoginCommand(
            username_or_email=self.username_or_email,
            password=self.password,
            user_agent=user_agent,
            ip_address=ip_address,
        )


class TokenResponse(BaseModel):
    """JSON returned by login and refresh endpoints.

    The refresh token is also set as an HttpOnly cookie by the endpoint.
    Returning it in the body too is convenient for non-browser clients.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int  # seconds — access TTL
