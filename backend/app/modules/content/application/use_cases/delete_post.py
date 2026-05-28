"""Soft-delete a post (author or moderator)."""

from __future__ import annotations

from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import DeletePostCommand
from app.modules.content.application.errors import (
    NotPostOwner,
    PostNotFound,
)
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.post import PostId
from app.modules.identity.domain.user import UserId


class DeletePostUseCase:
    """Mark a post as deleted; the row is kept for audit/notification context."""

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: DeletePostCommand) -> Result[None, DomainError]:
        post_id = PostId(cmd.post_public_id)
        actor_id = UserId(cmd.actor_public_id)

        async with self._uow as uow:
            post = await uow.posts.get(post_id)
            if post is None or post.is_deleted:
                return Err(PostNotFound(str(cmd.post_public_id)))
            if post.author_id != actor_id and not cmd.actor_can_moderate:
                return Err(NotPostOwner())

            post.soft_delete(deleted_by=actor_id)
            await uow.posts.add(post)
            await uow.commit()
            events = post.pull_events()

        for event in events:
            await self._bus.publish(event)
        return Ok(None)
