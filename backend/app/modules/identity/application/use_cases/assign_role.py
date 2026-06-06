"""Admin operations: assign / revoke roles."""

from __future__ import annotations

from app.modules.identity.application.commands import (
    AssignRoleCommand,
    RevokeRoleCommand,
)
from app.modules.identity.application.errors import RoleNotFound, UserNotFound
from app.modules.identity.application.ports import IIdentityUnitOfWork
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class AssignRoleUseCase:
    def __init__(self, uow: IIdentityUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: AssignRoleCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get(UserId(cmd.target_user_public_id))
            if user is None:
                return Err(UserNotFound(str(cmd.target_user_public_id)))
            role = await uow.roles.get_by_name(cmd.role_name)
            if role is None:
                return Err(RoleNotFound(cmd.role_name))
            user.assign_role(
                role, by=UserId(cmd.by_user_public_id) if cmd.by_user_public_id else None
            )
            await uow.commit()
            events = user.pull_events()

        for ev in events:
            await self._bus.publish(ev)
        return Ok(None)


class RevokeRoleUseCase:
    def __init__(self, uow: IIdentityUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: RevokeRoleCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get(UserId(cmd.target_user_public_id))
            if user is None:
                return Err(UserNotFound(str(cmd.target_user_public_id)))
            role = await uow.roles.get_by_name(cmd.role_name)
            if role is None:
                return Err(RoleNotFound(cmd.role_name))
            user.revoke_role(
                role, by=UserId(cmd.by_user_public_id) if cmd.by_user_public_id else None
            )
            await uow.commit()
            events = user.pull_events()

        for ev in events:
            await self._bus.publish(ev)
        return Ok(None)
