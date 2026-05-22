"""Refresh-token rotation with reuse detection.

Workflow per ``docs/03-security.md`` §2.3:

1. Decode the refresh JWT (signature + ``exp``).
2. Look up the persisted record by ``jti``.
3. If the record is *rotated*, the client has presented an already-used
   token — treat as theft, revoke the whole chain and publish
   :class:`RefreshTokenReuseDetected`.
4. Otherwise verify status, expiry, hash equality, user status.
5. Issue a new pair, mark the old token as rotated, store the new one.
"""

from __future__ import annotations

from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.identity.application.commands import (
    RefreshSessionCommand,
    TokenPair,
)
from app.modules.identity.application.errors import (
    InvalidRefreshToken,
    RefreshTokenReuseDetected,
    UserBlocked,
)
from app.modules.identity.application.ports import (
    IIdentityUnitOfWork,
    ITokenService,
)
from app.modules.identity.domain.events import (
    RefreshTokenIssued,
    RefreshTokenReuseDetected as RefreshTokenReuseDetectedEvent,
    RefreshTokenRotated,
)
from app.modules.identity.domain.refresh_token import TokenStatus


class RefreshSessionUseCase:
    """Rotate an existing refresh token into a fresh access+refresh pair."""

    def __init__(
        self,
        uow: IIdentityUnitOfWork,
        tokens: ITokenService,
        bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._bus = bus

    async def execute(
        self, cmd: RefreshSessionCommand
    ) -> Result[TokenPair, DomainError]:
        claims = self._tokens.decode_refresh(cmd.refresh_token)
        if claims is None:
            return Err(InvalidRefreshToken())

        events_after_commit: list = []

        async with self._uow as uow:
            stored = await uow.refresh_tokens.get_by_public_id(claims.token_public_id)
            if stored is None:
                return Err(InvalidRefreshToken())

            # --- reuse detection ---------------------------------------
            if stored.status == TokenStatus.ROTATED:
                await uow.refresh_tokens.revoke_chain_from(stored.id)
                await uow.refresh_tokens.revoke_all_for_user(stored.user_id)
                await uow.commit()
                await self._bus.publish(
                    RefreshTokenReuseDetectedEvent(
                        user_id=stored.user_id.value,
                        token_id=stored.id.value,
                    )
                )
                return Err(RefreshTokenReuseDetected())

            if stored.status != TokenStatus.ACTIVE or stored.is_expired:
                return Err(InvalidRefreshToken())

            if stored.token_hash != self._tokens.hash_token(cmd.refresh_token):
                # Token id matched but the actual JWT differs — likely tampered.
                return Err(InvalidRefreshToken())

            user = await uow.users.get(stored.user_id)
            if user is None:
                return Err(InvalidRefreshToken())
            if not user.is_active:
                return Err(UserBlocked())

            access = self._tokens.issue_access(user)
            new_refresh = self._tokens.issue_refresh(
                user, user_agent=cmd.user_agent, ip_address=cmd.ip_address
            )
            await uow.refresh_tokens.add(new_refresh.record)
            stored.rotate_to(new_refresh.record)
            await uow.refresh_tokens.save(stored)
            await uow.commit()

            events_after_commit.append(
                RefreshTokenRotated(
                    user_id=user.id.value,
                    old_token_id=stored.id.value,
                    new_token_id=new_refresh.record.id.value,
                )
            )
            events_after_commit.append(
                RefreshTokenIssued(
                    user_id=user.id.value,
                    token_id=new_refresh.record.id.value,
                )
            )

        for event in events_after_commit:
            await self._bus.publish(event)

        return Ok(
            TokenPair(
                access_token=access.jwt,
                refresh_token=new_refresh.jwt,
                expires_in=access.expires_in_seconds,
            )
        )
