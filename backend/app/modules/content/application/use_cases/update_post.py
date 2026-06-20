"""Edit an existing post (author or moderator)."""

from __future__ import annotations

from app.modules.content.application.commands import (
    PostSummary,
    UpdatePostCommand,
)
from app.modules.content.application.errors import (
    CategoryNotFound,
    NotPostOwner,
    PostNotFound,
)
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.category import CategoryId
from app.modules.content.domain.post import PostId
from app.modules.content.domain.tag import Tag
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
    Slug,
)
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class UpdatePostUseCase:
    """Apply partial updates to a post.

    Ownership and permission checks happen here, not in the dependency:
    the use case knows about ``actor_can_moderate`` and the post's author.
    """

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(self, cmd: UpdatePostCommand) -> Result[PostSummary, DomainError]:
        post_id = PostId(cmd.post_public_id)
        actor_id = UserId(cmd.actor_public_id)

        async with self._uow as uow:
            post = await uow.posts.get(post_id)
            if post is None or post.is_deleted:
                return Err(PostNotFound(str(cmd.post_public_id)))
            if post.author_id != actor_id and not cmd.actor_can_moderate:
                return Err(NotPostOwner())

            category_id: CategoryId | None = post.category_id
            if cmd.category_public_id is not None:
                category = await uow.categories.get(CategoryId(cmd.category_public_id))
                if category is None:
                    return Err(CategoryNotFound(str(cmd.category_public_id)))
                category_id = category.id

            content: MarkdownContent | None = None
            if cmd.content is not None or cmd.content_format is not None:
                fmt = (
                    ContentFormat(cmd.content_format)
                    if cmd.content_format is not None
                    else post.content.format
                )
                body = cmd.content if cmd.content is not None else post.content.body
                content = MarkdownContent(body=body, format=fmt)

            tags: set[Tag] | None = None
            if cmd.tag_names is not None:
                cleaned = [n.strip().lower() for n in cmd.tag_names if n.strip()]
                tags = set(await uow.tags.upsert_many_by_name(list(cleaned)))

            slug: Slug | None = None
            if cmd.title is not None:
                slug = Slug.from_text(cmd.title)

            post.edit(
                title=cmd.title,
                content=content,
                category_id=category_id,
                tags=tags,
                slug=slug,
                updated_by=actor_id,
            )
            await uow.posts.add(post)  # ``add`` doubles as upsert
            await uow.commit()
            summary = await uow.posts.get_with_summary(post.id)
            events = post.pull_events()

        assert summary is not None
        for event in events:
            await self._bus.publish(event)
        return Ok(summary)
