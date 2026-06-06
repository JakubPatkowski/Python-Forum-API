"""SQLAlchemy Unit of Work for the identity module.

Wraps a single SQLAlchemy ``Session`` in a transactional context and exposes
the three identity repositories as attributes. Use cases obtain the UoW from
DI and use it as an async context manager.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from app.modules.identity.application.ports import IIdentityUnitOfWork
from app.modules.identity.infrastructure.repositories import (
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyUserRepository,
)


class SqlAlchemyIdentityUnitOfWork(IIdentityUnitOfWork):
    """Per-request UoW. Construct one per HTTP request (or test).

    The session lifecycle is fully managed inside the ``async with`` block:
    a fresh session is opened on enter, committed/rolled-back on exit.
    """

    users: SqlAlchemyUserRepository
    roles: SqlAlchemyRoleRepository
    refresh_tokens: SqlAlchemyRefreshTokenRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self._session)
        self.roles = SqlAlchemyRoleRepository(self._session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None

    async def commit(self) -> None:
        assert self._session is not None, "UoW must be entered before commit"
        self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None, "UoW must be entered before rollback"
        self._session.rollback()
