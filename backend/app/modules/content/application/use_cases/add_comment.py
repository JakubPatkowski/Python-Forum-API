"""Add a comment to a post (top-level or reply)."""

from __future__ import annotations

from app.config import settings
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import (
    AddCommentCommand,
    CommentSummary,
)
from app.modules.content.application.errors import (
    CommentNotFound,
    PostNotFound,
)
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.comment import Comment, CommentId
from app.modules.content.domain.post import PostId
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
)
from app.modules.identity.domain.user import UserId


class AddCommentUseCase:
    """Insert a new comment.

    The materialized ``path`` is finalised by the repository once it knows
    the row's serial id — the use case only validates depth.
    """

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(
        self, cmd: AddCommentCommand
    ) -> Result[CommentSummary, DomainError]:
        fmt = ContentFormat(cmd.content_format)
        content = MarkdownContent(body=cmd.content, format=fmt)
        author_id = UserId(cmd.author_public_id)
        post_id = PostId(cmd.post_public_id)

        async with self._uow as uow:
            post = await uow.posts.get(post_id)
            if post is None or post.is_deleted:
                return Err(PostNotFound(str(cmd.post_public_id)))

            parent: Comment | None = None
            if cmd.parent_comment_public_id is not None:
                parent = await uow.comments.get(
                    CommentId(cmd.parent_comment_public_id)
                )
                if parent is None:
                    return Err(
                        CommentNotFound(str(cmd.parent_comment_public_id))
                    )
                if parent.post_id != post_id:
                    return Err(
                        CommentNotFound(str(cmd.parent_comment_public_id))
                    )

            comment = Comment.create(
                post_id=post_id,
                author_id=author_id,
                content=content,
                parent=parent,
                max_depth=settings.MAX_COMMENT_DEPTH,
            )
            await uow.comments.add(comment)
            await uow.commit()
            summary = await uow.comments.get_with_summary(comment.id)
            events = comment.pull_events()

        assert summary is not None  # noqa: S101
        for event in events:
            await self._bus.publish(event)
        return Ok(summary)
