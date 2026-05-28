"""List posts with keyset pagination."""

from __future__ import annotations

from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import (
    ListPostsQuery,
    PostListPage,
)
from app.modules.content.application.pagination import PostCursor
from app.modules.content.application.ports import IContentUnitOfWork


class ListPostsUseCase:
    """Paginate posts ordered by ``created_at`` descending.

    A ``None`` cursor returns the freshest page; the response contains a
    ``next_cursor`` if more results exist.
    """

    DEFAULT_LIMIT: int = 20
    MAX_LIMIT: int = 100

    def __init__(self, uow: IContentUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, q: ListPostsQuery
    ) -> Result[PostListPage, DomainError]:
        limit = max(1, min(q.limit or self.DEFAULT_LIMIT, self.MAX_LIMIT))
        cursor = PostCursor.decode(q.cursor) if q.cursor else None

        async with self._uow as uow:
            page = await uow.posts.list_summaries(
                limit=limit,
                cursor_created_at=cursor.created_at if cursor else None,
                cursor_id=cursor.public_id if cursor else None,
                category_public_id=q.category_public_id,
                tag_slug=q.tag_slug,
                author_public_id=q.author_public_id,
            )
        return Ok(page)


__all__ = ["ListPostsUseCase"]


def _err(error: DomainError) -> Err[DomainError]:
    """Helper for type-checkers when a use case wants to short-circuit."""
    return Err(error)
