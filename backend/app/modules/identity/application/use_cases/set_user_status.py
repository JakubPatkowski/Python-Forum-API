"""Block or unblock a user account."""

from __future__ import annotations

from app.modules.identity.application.commands import SetUserStatusCommand
from app.modules.identity.application.errors import UserNotFound
from app.modules.identity.application.ports import IIdentityUnitOfWork
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class SetUserStatusUseCase:
    def __init__(self, uow: IIdentityUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: SetUserStatusCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get(UserId(cmd.target_user_public_id))
            if user is None:
                return Err(UserNotFound(str(cmd.target_user_public_id)))
            actor = UserId(cmd.by_user_public_id) if cmd.by_user_public_id else None
            if cmd.blocked:
                user.block(by=actor)
                # Revoke all sessions when blocking.
                await uow.refresh_tokens.revoke_all_for_user(user.id)
            else:
                user.unblock(by=actor)
            await uow.commit()
            events = user.pull_events()

        for ev in events:
            await self._bus.publish(ev)
        return Ok(None)
