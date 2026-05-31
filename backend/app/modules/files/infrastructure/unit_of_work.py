"""SQLAlchemy Unit of Work for the files module.

Owns one ``Session`` per request and exposes the file repository plus the
cross-module helpers the use cases need (resolving public UUIDs to the legacy
integer FKs, reading post/comment authors, and reading/writing the
``users.avatar_file_id`` link). This mirrors the content UoW's pragmatic
cross-module DB access.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.models.category import Category as CategoryOrm
from app.models.comment import Comment as CommentOrm
from app.models.post import Post as PostOrm
from app.models.user import User as UserOrm
from app.modules.files.application.ports import IFilesUnitOfWork
from app.modules.files.domain.value_objects import FileOwnerType
from app.modules.files.infrastructure.orm import FileOrm
from app.modules.files.infrastructure.repositories import SqlAlchemyFileRepository


class SqlAlchemyFilesUnitOfWork(IFilesUnitOfWork):
    """Per-request UoW for the files module."""

    files: SqlAlchemyFileRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._user_cache: dict[UUID, int] = {}

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.files = SqlAlchemyFileRepository(
            self._session,
            user_id_resolver=self._sync_resolve_user,
            post_id_resolver=self._sync_resolve_post,
            comment_id_resolver=self._sync_resolve_comment,
            category_id_resolver=self._sync_resolve_category,
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
            self._user_cache.clear()

    async def commit(self) -> None:
        assert self._session is not None, "UoW must be entered before commit"
        self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None, "UoW must be entered before rollback"
        self._session.rollback()

    # --- cross-module resolvers --------------------------------------------

    async def resolve_user_id(self, user_public_id: UUID) -> int | None:
        return self._sync_resolve_user(user_public_id)

    async def file_internal_id(self, file_public_id: UUID) -> int | None:
        return self._session_required().scalar(
            select(FileOrm.id).where(FileOrm.public_id == file_public_id)
        )

    async def get_post_author(self, post_public_id: UUID) -> UUID | None:
        return self._session_required().scalar(
            select(UserOrm.public_id)
            .join(PostOrm, PostOrm.author_id == UserOrm.id)
            .where(PostOrm.public_id == post_public_id)
        )

    async def get_comment_author(self, comment_public_id: UUID) -> UUID | None:
        return self._session_required().scalar(
            select(UserOrm.public_id)
            .join(CommentOrm, CommentOrm.author_id == UserOrm.id)
            .where(CommentOrm.public_id == comment_public_id)
        )

    async def category_exists(self, category_public_id: UUID) -> bool:
        return self._sync_resolve_category(category_public_id) is not None

    # --- avatar / category image -------------------------------------------

    async def set_user_avatar(
        self, user_public_id: UUID, file_internal_id: int | None
    ) -> None:
        self._session_required().execute(
            update(UserOrm)
            .where(UserOrm.public_id == user_public_id)
            .values(avatar_file_id=file_internal_id)
        )

    async def current_avatar_file_public_id(
        self, user_public_id: UUID
    ) -> UUID | None:
        return self._session_required().scalar(
            select(FileOrm.public_id)
            .join(UserOrm, UserOrm.avatar_file_id == FileOrm.id)
            .where(UserOrm.public_id == user_public_id)
        )

    async def current_category_image_file_public_id(
        self, category_public_id: UUID
    ) -> UUID | None:
        category_id = self._sync_resolve_category(category_public_id)
        if category_id is None:
            return None
        return self._session_required().scalar(
            select(FileOrm.public_id)
            .where(
                FileOrm.owner_category_id == category_id,
                FileOrm.owner_type == FileOwnerType.CATEGORY,
            )
            .order_by(FileOrm.created_at.desc())
            .limit(1)
        )

    # --- internal sync resolvers -------------------------------------------

    def _session_required(self) -> Session:
        assert self._session is not None, "UoW must be entered"
        return self._session

    def _sync_resolve_user(self, public_id: UUID) -> int | None:
        cached = self._user_cache.get(public_id)
        if cached is not None:
            return cached
        db_id = self._session_required().scalar(
            select(UserOrm.id).where(UserOrm.public_id == public_id)
        )
        if db_id is not None:
            self._user_cache[public_id] = db_id
        return db_id

    def _sync_resolve_post(self, public_id: UUID) -> int | None:
        return self._session_required().scalar(
            select(PostOrm.id).where(PostOrm.public_id == public_id)
        )

    def _sync_resolve_comment(self, public_id: UUID) -> int | None:
        return self._session_required().scalar(
            select(CommentOrm.id).where(CommentOrm.public_id == public_id)
        )

    def _sync_resolve_category(self, public_id: UUID) -> int | None:
        return self._session_required().scalar(
            select(CategoryOrm.id).where(CategoryOrm.public_id == public_id)
        )
