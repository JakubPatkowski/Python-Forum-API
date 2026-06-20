"""Register a brand-new user.

Steps:
1. Construct value objects (validation happens in their ``__post_init__``).
2. Confirm username and email are not taken.
3. Hash the password.
4. Resolve the default ``user`` role.
5. Create the ``User`` aggregate, persist it, commit, publish events.
"""

from __future__ import annotations

from app.modules.identity.application.commands import (
    RegisterUserCommand,
    UserSummary,
)
from app.modules.identity.application.errors import (
    EmailAlreadyTaken,
    RoleNotFound,
    UsernameAlreadyTaken,
)
from app.modules.identity.application.ports import (
    IIdentityUnitOfWork,
    IPasswordHasher,
)
from app.modules.identity.domain.user import User
from app.modules.identity.domain.value_objects import Email, RawPassword, Username
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class RegisterUserUseCase:
    """Create a new user account."""

    DEFAULT_ROLE_NAME = "user"

    def __init__(
        self,
        uow: IIdentityUnitOfWork,
        hasher: IPasswordHasher,
        bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._bus = bus

    async def execute(self, cmd: RegisterUserCommand) -> Result[UserSummary, DomainError]:
        # Value-object construction validates the inputs.
        username = Username(cmd.username)
        email = Email(cmd.email)
        raw_password = RawPassword(cmd.password)

        async with self._uow as uow:
            if await uow.users.get_by_username(username):
                return Err(UsernameAlreadyTaken(username.value))
            if await uow.users.get_by_email(email):
                return Err(EmailAlreadyTaken(email.value))

            default_role = await uow.roles.get_by_name(self.DEFAULT_ROLE_NAME)
            if default_role is None:
                return Err(RoleNotFound(self.DEFAULT_ROLE_NAME))

            user = User.register(
                username=username,
                email=email,
                password_hash=self._hasher.hash(raw_password.value),
                default_role=default_role,
            )
            await uow.users.add(user)
            await uow.commit()
            events = user.pull_events()

        for event in events:
            await self._bus.publish(event)

        return Ok(
            UserSummary(
                public_id=user.id.value,
                username=str(user.username),
                email=str(user.email),
                is_active=user.is_active,
                roles=tuple(r.name for r in user.roles),
                permissions=tuple(p.code for p in user.effective_permissions()),
            )
        )
