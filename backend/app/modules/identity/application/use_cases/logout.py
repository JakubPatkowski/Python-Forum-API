"""Logout use cases: drop the current refresh token, or all of them."""

from __future__ import annotations

from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.identity.application.commands import (
    LogoutAllCommand,
    LogoutCommand,
)
from app.modules.identity.application.errors import UserNotFound
from app.modules.identity.application.ports import (
    IIdentityUnitOfWork,
    ITokenService,
)
from app.modules.identity.domain.events import UserLoggedOut
from app.modules.identity.domain.user import UserId


class LogoutUseCase:
    """Revoke a single refresh token (the one the client presents).

    Missing / invalid tokens are silently treated as logged out so the
    endpoint is idempotent and never leaks information.
    """

    def __init__(
        self,
        uow: IIdentityUnitOfWork,
        tokens: ITokenService,
        bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._bus = bus

    async def execute(self, cmd: LogoutCommand) -> Result[None, DomainError]:
        if not cmd.refresh_token:
            return Ok(None)
        claims = self._tokens.decode_refresh(cmd.refresh_token)
        if claims is None:
            return Ok(None)

        async with self._uow as uow:
            stored = await uow.refresh_tokens.get_by_public_id(claims.token_public_id)
            if stored is None:
                return Ok(None)
            # Defence-in-depth: only the token owner can revoke it.
            if stored.user_id.value != cmd.user_public_id:
                return Ok(None)
            stored.revoke()
            await uow.refresh_tokens.save(stored)
            await uow.commit()

        await self._bus.publish(
            UserLoggedOut(
                user_id=cmd.user_public_id,
                token_id=claims.token_public_id,
            )
        )
        return Ok(None)


class LogoutAllUseCase:
    """Revoke all refresh tokens for the current user."""

    def __init__(
        self,
        uow: IIdentityUnitOfWork,
        bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: LogoutAllCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get(UserId(cmd.user_public_id))
            if user is None:
                return Err(UserNotFound(str(cmd.user_public_id)))
            await uow.refresh_tokens.revoke_all_for_user(user.id)
            await uow.commit()

        await self._bus.publish(UserLoggedOut(user_id=cmd.user_public_id))
        return Ok(None)
