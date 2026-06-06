"""SQLAlchemy Unit of Work for the content module.

Holds one ``Session`` per request scope and exposes four repositories:
posts, comments, categories, tags. The UoW also offers a tiny helper
``resolve_user_id`` so the repositories can translate a user UUID into
the legacy integer ``users.id`` without each repository re-implementing
the same lookup.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.user import User as UserOrm
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.infrastructure.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyCommentRepository,
    SqlAlchemyPostRepository,
    SqlAlchemyTagRepository,
)


class SqlAlchemyContentUnitOfWork(IContentUnitOfWork):
    """Per-request UoW. Construct one per HTTP request (or test).

    Manages the SQLAlchemy ``Session`` lifecycle: opened on ``__aenter__``,
    rolled back if the body raised, then closed.
    """

    posts: SqlAlchemyPostRepository
    comments: SqlAlchemyCommentRepository
    categories: SqlAlchemyCategoryRepository
    tags: SqlAlchemyTagRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._user_id_cache: dict[UUID, int] = {}

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.tags = SqlAlchemyTagRepository(self._session)
        self.categories = SqlAlchemyCategoryRepository(self._session)
        self.posts = SqlAlchemyPostRepository(
            self._session, user_id_resolver=self._sync_resolve_user_id
        )
        self.comments = SqlAlchemyCommentRepository(
            self._session, user_id_resolver=self._sync_resolve_user_id
        )
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
            self._user_id_cache.clear()

    async def commit(self) -> None:
        assert self._session is not None, "UoW must be entered before commit"
        self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None, "UoW must be entered before rollback"
        self._session.rollback()

    async def resolve_user_id(self, user_public_id: UUID) -> int | None:
        """Async port method — delegates to the sync resolver."""
        return self._sync_resolve_user_id(user_public_id)

    # --- internal ----------------------------------------------------------

    def _sync_resolve_user_id(self, user_public_id: UUID) -> int | None:
        """Translate a user UUID into ``users.id``, memoised per session."""
        cached = self._user_id_cache.get(user_public_id)
        if cached is not None:
            return cached
        assert self._session is not None
        db_id = self._session.scalar(
            select(UserOrm.id).where(UserOrm.public_id == user_public_id)
        )
        if db_id is not None:
            self._user_id_cache[user_public_id] = db_id
        return db_id
