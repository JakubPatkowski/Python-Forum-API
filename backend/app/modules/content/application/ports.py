"""Ports (interfaces) consumed by content use cases.

The application layer talks to the database through these protocols; the
infrastructure layer provides concrete SQLAlchemy implementations.

Note: query projections (``PostSummary``, ``CommentSummary``, ``PostListPage``)
live in :mod:`commands` to keep them next to the use-case contract.
"""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.shared.application.repository import IRepository

from app.modules.content.application.commands import (
    CategorySummary,
    CommentSummary,
    PostListPage,
    PostSummary,
)
from app.modules.content.domain.category import Category, CategoryId
from app.modules.content.domain.comment import Comment, CommentId
from app.modules.content.domain.post import Post, PostId
from app.modules.content.domain.tag import Tag, TagId

# --------------------------------------------------------------------------- #
# Repositories                                                                #
# --------------------------------------------------------------------------- #


class IPostRepository(IRepository[Post, PostId], Protocol):
    """Persistence port for :class:`Post` aggregates."""

    async def get_with_summary(self, id_: PostId) -> PostSummary | None:
        """Load a post and join the metadata needed to project a summary."""

    async def has_slug_for_author(
        self, *, author_public_id: UUID, slug: str, exclude_id: PostId | None = None
    ) -> bool:
        """Check whether an author already owns a post with this slug."""

    async def list_summaries(
        self,
        *,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
        category_public_id: UUID | None = None,
        tag_slug: str | None = None,
        author_public_id: UUID | None = None,
    ) -> PostListPage:
        """Return a keyset-paginated page of post summaries.

        The cursor compares ``(created_at DESC, public_id DESC)`` so the
        repository knows how to fetch the rows strictly older than the
        cursor.
        """


class ICommentRepository(IRepository[Comment, CommentId], Protocol):
    """Persistence port for :class:`Comment` aggregates."""

    async def get_with_summary(self, id_: CommentId) -> CommentSummary | None: ...

    async def parent_path_for(
        self, parent_id: CommentId
    ) -> tuple[str, int] | None:
        """Return ``(path, depth)`` of an existing parent comment, if any."""

    async def list_tree_for_post(
        self, post_public_id: UUID
    ) -> list[CommentSummary]:
        """Return the entire tree of a post sorted DFS by ``path``."""

    async def save(self, comment: Comment) -> None:
        """Persist mutations on an already-loaded comment (edit / delete)."""


class ICategoryRepository(IRepository[Category, CategoryId], Protocol):
    """Persistence port for :class:`Category`."""

    async def get_by_name(self, name: str) -> Category | None: ...

    async def get_by_slug(self, slug: str) -> Category | None: ...

    async def list_all(self) -> list[CategorySummary]: ...


class ITagRepository(Protocol):
    """Persistence port for :class:`Tag`. Tags are write-light, read-heavy."""

    async def get_by_name(self, name: str) -> Tag | None: ...

    async def get_by_slug(self, slug: str) -> Tag | None: ...

    async def get(self, id_: TagId) -> Tag | None: ...

    async def add(self, tag: Tag) -> None: ...

    async def upsert_many_by_name(self, names: list[str]) -> list[Tag]:
        """Return a Tag for every name, creating missing ones."""

    async def list_all(self) -> list[Tag]: ...


# --------------------------------------------------------------------------- #
# Unit of Work                                                                #
# --------------------------------------------------------------------------- #


class IContentUnitOfWork(Protocol):
    """Transactional scope grouping content repositories.

    Use cases enter the UoW, perform writes through the repositories, then
    call ``commit()``. Domain events are pulled from aggregates and published
    by the use case *after* the commit.
    """

    posts: IPostRepository
    comments: ICommentRepository
    categories: ICategoryRepository
    tags: ITagRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def resolve_user_id(self, user_public_id: UUID) -> int | None:
        """Translate a user UUID into the legacy integer ``users.id``.

        Comments and posts persist ``author_id`` as the legacy integer FK; the
        UoW gives the repositories a shared resolver so they do not each
        re-implement the lookup.
        """
