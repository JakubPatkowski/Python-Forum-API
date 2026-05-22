"""Login use case — verify credentials and issue an access+refresh pair."""

from __future__ import annotations

from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.identity.application.commands import LoginCommand, TokenPair
from app.modules.identity.application.errors import (
    InvalidCredentials,
    UserBlocked,
)
from app.modules.identity.application.ports import (
    IIdentityUnitOfWork,
    IPasswordHasher,
    ITokenService,
)
from app.modules.identity.domain.events import RefreshTokenIssued


class LoginUseCase:
    """Authenticate by username/email + password, issue a token pair."""

    def __init__(
        self,
        uow: IIdentityUnitOfWork,
        hasher: IPasswordHasher,
        tokens: ITokenService,
        bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._bus = bus

    async def execute(self, cmd: LoginCommand) -> Result[TokenPair, DomainError]:
        async with self._uow as uow:
            user = await uow.users.get_by_username_or_email(cmd.username_or_email)
            # Generic "invalid credentials" — never tell whether the username
            # or the password was wrong (timing attack mitigated by Argon2).
            if user is None:
                return Err(InvalidCredentials())
            if not self._hasher.verify(user.password_hash, cmd.password):
                return Err(InvalidCredentials())
            if not user.is_active:
                return Err(UserBlocked())

            # Rotate the password hash on the fly if Argon2 parameters changed.
            if self._hasher.needs_rehash(user.password_hash):
                user.change_password(self._hasher.hash(cmd.password))

            access = self._tokens.issue_access(user)
            refresh = self._tokens.issue_refresh(
                user, user_agent=cmd.user_agent, ip_address=cmd.ip_address
            )
            await uow.refresh_tokens.add(refresh.record)
            await uow.commit()

            issued_event = RefreshTokenIssued(
                user_id=user.id.value,
                token_id=refresh.record.id.value,
            )

        await self._bus.publish(issued_event)
        return Ok(
            TokenPair(
                access_token=access.jwt,
                refresh_token=refresh.jwt,
                expires_in=access.expires_in_seconds,
            )
        )
