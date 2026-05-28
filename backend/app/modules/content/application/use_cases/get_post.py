"""Fetch a single post by its public UUID."""

from __future__ import annotations

from uuid import UUID

from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import PostSummary
from app.modules.content.application.errors import PostNotFound
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.post import PostId


class GetPostUseCase:
    """Return the post summary for the given UUID, or ``PostNotFound``."""

    def __init__(self, uow: IContentUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, post_public_id: UUID) -> Result[PostSummary, DomainError]:
        async with self._uow as uow:
            summary = await uow.posts.get_with_summary(PostId(post_public_id))
        if summary is None or summary.is_deleted:
            return Err(PostNotFound(str(post_public_id)))
        return Ok(summary)
