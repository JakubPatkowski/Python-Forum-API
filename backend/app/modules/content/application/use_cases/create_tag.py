"""Create a tag explicitly (moderator+).

In normal operation tags are created on the fly when a post references a
new name; this use case exists for the moderator UI and for seeding.
"""

from __future__ import annotations

from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import (
    CreateTagCommand,
    TagSummary,
)
from app.modules.content.application.errors import TagAlreadyExists
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.events import TagCreated
from app.modules.content.domain.tag import Tag


class CreateTagUseCase:
    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(
        self, cmd: CreateTagCommand
    ) -> Result[TagSummary, DomainError]:
        name = cmd.name.strip().lower()

        async with self._uow as uow:
            if await uow.tags.get_by_name(name) is not None:
                return Err(TagAlreadyExists(name))
            tag = Tag.create(name)
            await uow.tags.add(tag)
            await uow.commit()
            await self._bus.publish(
                TagCreated(tag_id=tag.id.value, name=tag.name, slug=str(tag.slug))
            )
        return Ok(
            TagSummary(public_id=tag.id.value, name=tag.name, slug=str(tag.slug))
        )
