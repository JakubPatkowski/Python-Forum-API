"""Admin operations: grant / deny per-user permission overrides."""

from __future__ import annotations

from app.modules.identity.application.commands import (
    DenyPermissionCommand,
    GrantPermissionCommand,
)
from app.modules.identity.application.errors import UserNotFound
from app.modules.identity.application.ports import IIdentityUnitOfWork
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class GrantPermissionUseCase:
    def __init__(self, uow: IIdentityUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: GrantPermissionCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get(UserId(cmd.target_user_public_id))
            if user is None:
                return Err(UserNotFound(str(cmd.target_user_public_id)))
            user.grant_permission(
                Permission(cmd.permission_code),
                by=UserId(cmd.by_user_public_id) if cmd.by_user_public_id else None,
            )
            await uow.commit()
            events = user.pull_events()

        for ev in events:
            await self._bus.publish(ev)
        return Ok(None)


class DenyPermissionUseCase:
    def __init__(self, uow: IIdentityUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: DenyPermissionCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get(UserId(cmd.target_user_public_id))
            if user is None:
                return Err(UserNotFound(str(cmd.target_user_public_id)))
            user.deny_permission(
                Permission(cmd.permission_code),
                by=UserId(cmd.by_user_public_id) if cmd.by_user_public_id else None,
            )
            await uow.commit()
            events = user.pull_events()

        for ev in events:
            await self._bus.publish(ev)
        return Ok(None)
