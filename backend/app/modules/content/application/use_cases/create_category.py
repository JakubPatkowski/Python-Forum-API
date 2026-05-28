"""Create a new category (moderator+)."""

from __future__ import annotations

from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import (
    CategorySummary,
    CreateCategoryCommand,
)
from app.modules.content.application.errors import CategoryAlreadyExists
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.category import Category, CategoryId
from app.modules.content.domain.events import CategoryCreated
from app.modules.content.domain.value_objects import Slug


class CreateCategoryUseCase:
    """Persist a brand-new category."""

    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(
        self, cmd: CreateCategoryCommand
    ) -> Result[CategorySummary, DomainError]:
        name = cmd.name.strip()
        slug = Slug(cmd.slug) if cmd.slug else Slug.from_text(name)

        async with self._uow as uow:
            if await uow.categories.get_by_name(name) is not None:
                return Err(CategoryAlreadyExists(name))
            if await uow.categories.get_by_slug(str(slug)) is not None:
                return Err(CategoryAlreadyExists(name))

            category = Category(
                id=CategoryId.new(),
                name=name,
                slug=slug,
                description=cmd.description,
            )
            await uow.categories.add(category)
            await uow.commit()

            await self._bus.publish(
                CategoryCreated(
                    category_id=category.id.value,
                    name=category.name,
                    slug=str(category.slug),
                )
            )

        return Ok(
            CategorySummary(
                public_id=category.id.value,
                name=category.name,
                slug=str(category.slug),
                description=category.description,
                created_at=category.created_at,
            )
        )
