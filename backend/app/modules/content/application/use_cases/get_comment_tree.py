"""Return the full comment tree for a post in DFS order."""

from __future__ import annotations

from uuid import UUID

from app.modules.content.application.commands import CommentSummary
from app.modules.content.application.errors import PostNotFound
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.post import PostId
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class GetCommentTreeUseCase:
    """List every comment under a post sorted DFS by ``path``.

    The repository performs a single ``ORDER BY path`` query — no recursion.
    Callers receive the flat list and can reconstruct the tree client-side
    using ``depth``.
    """

    def __init__(self, uow: IContentUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, post_public_id: UUID) -> Result[list[CommentSummary], DomainError]:
        async with self._uow as uow:
            # Use the lightweight summary projection instead of hydrating the
            # full Post aggregate (category + tags + author) — we only need to
            # know the post exists and is not soft-deleted.
            post = await uow.posts.get_with_summary(PostId(post_public_id))
            if post is None or post.is_deleted:
                return Err(PostNotFound(str(post_public_id)))
            tree = await uow.comments.list_tree_for_post(post_public_id)
        return Ok(tree)
