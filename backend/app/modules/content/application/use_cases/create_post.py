"""Create a brand-new post."""

from __future__ import annotations

from app.modules.content.application.commands import (
    CreatePostCommand,
    PostSummary,
)
from app.modules.content.application.errors import (
    CategoryNotFound,
    SlugAlreadyTaken,
)
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.post import Post
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


class CreatePostUseCase:
    """Persist a new :class:`Post` aggregate.

    Permission ``post.create`` is enforced in the presentation layer; the
    use case assumes the caller is allowed to create posts.
    """

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(
        self, cmd: CreatePostCommand
    ) -> Result[PostSummary, DomainError]:
        title = cmd.title.strip()
        fmt = ContentFormat(cmd.content_format)
        content = MarkdownContent(body=cmd.content, format=fmt)
        slug = Slug.from_text(title)
        author_id = UserId(cmd.author_public_id)

        async with self._uow as uow:
            category = None
            if cmd.category_public_id is not None:
                # Loading by domain id reuses the repository contract.
                from app.modules.content.domain.category import CategoryId

                category = await uow.categories.get(
                    CategoryId(cmd.category_public_id)
                )
                if category is None:
                    return Err(CategoryNotFound(str(cmd.category_public_id)))

            if await uow.posts.has_slug_for_author(
                author_public_id=author_id.value, slug=str(slug)
            ):
                return Err(SlugAlreadyTaken(str(slug)))

            tags: set[Tag] = set()
            if cmd.tag_names:
                cleaned_names = [n.strip().lower() for n in cmd.tag_names if n.strip()]
                if cleaned_names:
                    tags = set(
                        await uow.tags.upsert_many_by_name(list(cleaned_names))
                    )

            post = Post.create(
                author_id=author_id,
                title=title,
                content=content,
                category_id=category.id if category else None,
                tags=tags,
                slug=slug,
            )
            await uow.posts.add(post)
            await uow.commit()
            summary = await uow.posts.get_with_summary(post.id)
            events = post.pull_events()

        assert summary is not None, "Post must be loadable right after insert"
        for event in events:
            await self._bus.publish(event)
        return Ok(summary)
