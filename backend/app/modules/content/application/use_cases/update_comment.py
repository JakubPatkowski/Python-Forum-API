"""Edit a comment's body."""

from __future__ import annotations

from app.modules.content.application.commands import (
    CommentSummary,
    UpdateCommentCommand,
)
from app.modules.content.application.errors import (
    CommentNotFound,
    NotCommentOwner,
)
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.comment import CommentId
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
)
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class UpdateCommentUseCase:
    """Edit the body of a comment. Author or moderator."""

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: UpdateCommentCommand) -> Result[CommentSummary, DomainError]:
        comment_id = CommentId(cmd.comment_public_id)
        actor_id = UserId(cmd.actor_public_id)

        async with self._uow as uow:
            comment = await uow.comments.get(comment_id)
            if comment is None or comment.is_deleted:
                return Err(CommentNotFound(str(cmd.comment_public_id)))
            if comment.author_id != actor_id and not cmd.actor_can_moderate:
                return Err(NotCommentOwner())

            fmt = (
                ContentFormat(cmd.content_format)
                if cmd.content_format is not None
                else comment.content.format
            )
            comment.edit(
                content=MarkdownContent(body=cmd.content, format=fmt),
                updated_by=actor_id,
            )
            await uow.comments.save(comment)
            await uow.commit()
            summary = await uow.comments.get_with_summary(comment.id)
            events = comment.pull_events()

        assert summary is not None
        for event in events:
            await self._bus.publish(event)
        return Ok(summary)
