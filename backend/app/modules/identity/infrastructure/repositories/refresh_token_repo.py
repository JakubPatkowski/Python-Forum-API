"""SqlAlchemy implementation of :class:`IRefreshTokenRepository`.

The repository owns the integer FK <-> UUID translation:
- ``users.id`` (int) is internal,
- ``UserId`` (UUID) is the domain identity.

Domain state changes (rotate / revoke) are persisted via :meth:`save`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.identity.application.ports import IRefreshTokenRepository
from app.modules.identity.domain.refresh_token import (
    RefreshToken,
    RefreshTokenId,
)
from app.modules.identity.domain.user import UserId
from app.modules.identity.infrastructure.mappers import refresh_token_from_orm
from app.modules.identity.infrastructure.orm import RefreshTokenOrm, UserOrm


class SqlAlchemyRefreshTokenRepository(IRefreshTokenRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- IRepository --------------------------------------------------------

    async def get(self, id_: RefreshTokenId) -> RefreshToken | None:
        return await self.get_by_public_id(id_.value)

    async def add(self, entity: RefreshToken) -> None:
        user_int_id = self._resolve_user_int_id(entity.user_id)
        row = RefreshTokenOrm(
            public_id=entity.id.value,
            user_id=user_int_id,
            token_hash=entity.token_hash,
            status=entity.status.value,
            issued_at=entity.issued_at,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            user_agent=entity.user_agent,
            ip_address=entity.ip_address,
        )
        self._session.add(row)
        self._session.flush()

    async def remove(self, entity: RefreshToken) -> None:
        self._session.execute(
            RefreshTokenOrm.__table__.delete().where(RefreshTokenOrm.public_id == entity.id.value)
        )

    async def exists(self, id_: RefreshTokenId) -> bool:
        return (
            self._session.scalar(
                select(RefreshTokenOrm.id).where(RefreshTokenOrm.public_id == id_.value)
            )
            is not None
        )

    # --- IRefreshTokenRepository -------------------------------------------

    async def get_by_public_id(self, public_id: UUID) -> RefreshToken | None:
        row = self._session.scalar(
            select(RefreshTokenOrm).where(RefreshTokenOrm.public_id == public_id)
        )
        if row is None:
            return None
        user_public_id = self._session.scalar(
            select(UserOrm.public_id).where(UserOrm.id == row.user_id)
        )
        if user_public_id is None:
            return None
        return refresh_token_from_orm(row, user_public_id=user_public_id)

    async def save(self, token: RefreshToken) -> None:
        """Apply domain mutations (status, revoked_at, replaced_by) to the row."""
        row = self._session.scalar(
            select(RefreshTokenOrm).where(RefreshTokenOrm.public_id == token.id.value)
        )
        if row is None:
            return
        row.status = token.status.value
        row.revoked_at = token.revoked_at
        if token.replaced_by_id is not None:
            replaced_int = self._session.scalar(
                select(RefreshTokenOrm.id).where(
                    RefreshTokenOrm.public_id == token.replaced_by_id.value
                )
            )
            if replaced_int is not None:
                row.replaced_by = replaced_int

    async def revoke_chain_from(self, token_id: RefreshTokenId) -> None:
        """Revoke ``token_id`` and every descendant in its rotation chain."""
        start_int = self._session.scalar(
            select(RefreshTokenOrm.id).where(RefreshTokenOrm.public_id == token_id.value)
        )
        if start_int is None:
            return

        chain_ids: set[int] = {start_int}
        frontier: list[int] = [start_int]
        while frontier:
            next_rows = (
                self._session.execute(
                    select(RefreshTokenOrm.id).where(RefreshTokenOrm.replaced_by.in_(frontier))
                )
                .scalars()
                .all()
            )
            new_ids = set(next_rows) - chain_ids
            if not new_ids:
                break
            chain_ids.update(new_ids)
            frontier = list(new_ids)

        self._session.execute(
            update(RefreshTokenOrm)
            .where(RefreshTokenOrm.id.in_(chain_ids))
            .values(status="revoked", revoked_at=datetime.now(UTC))
        )

    async def revoke_all_for_user(self, user_id: UserId) -> None:
        user_int_id = self._resolve_user_int_id(user_id, raise_if_missing=False)
        if user_int_id is None:
            return
        self._session.execute(
            update(RefreshTokenOrm)
            .where((RefreshTokenOrm.user_id == user_int_id) & (RefreshTokenOrm.status != "revoked"))
            .values(status="revoked", revoked_at=datetime.now(UTC))
        )

    # --- internal -----------------------------------------------------------

    def _resolve_user_int_id(self, user_id: UserId, *, raise_if_missing: bool = True) -> int | None:
        result = self._session.scalar(select(UserOrm.id).where(UserOrm.public_id == user_id.value))
        if result is None and raise_if_missing:
            raise RuntimeError(f"Cannot persist refresh token: user {user_id} not found")
        return result
