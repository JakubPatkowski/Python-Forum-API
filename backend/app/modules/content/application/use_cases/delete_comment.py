"""Soft-delete a comment so its descendants stay reachable."""

from __future__ import annotations

from app.modules.content.application.commands import DeleteCommentCommand
from app.modules.content.application.errors import (
    CommentNotFound,
    NotCommentOwner,
)
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.comment import CommentId
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class DeleteCommentUseCase:
    """Mark a comment as deleted; the row stays so children are still reachable."""

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(
        self, cmd: DeleteCommentCommand
    ) -> Result[None, DomainError]:
        comment_id = CommentId(cmd.comment_public_id)
        actor_id = UserId(cmd.actor_public_id)

        async with self._uow as uow:
            comment = await uow.comments.get(comment_id)
            if comment is None or comment.is_deleted:
                return Err(CommentNotFound(str(cmd.comment_public_id)))
            if comment.author_id != actor_id and not cmd.actor_can_moderate:
                return Err(NotCommentOwner())

            comment.soft_delete(deleted_by=actor_id)
            await uow.comments.save(comment)
            await uow.commit()
            events = comment.pull_events()

        for event in events:
            await self._bus.publish(event)
        return Ok(None)
