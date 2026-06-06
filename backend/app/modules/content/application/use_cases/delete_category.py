"""Delete a category (moderator+).

Posts that referenced the category have their ``category_id`` set to NULL
(``ON DELETE SET NULL`` on the FK).
"""

from __future__ import annotations

from app.modules.content.application.commands import DeleteCategoryCommand
from app.modules.content.application.errors import CategoryNotFound
from app.modules.content.application.ports import IContentUnitOfWork
from app.modules.content.domain.category import CategoryId
from app.modules.content.domain.events import CategoryDeleted
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class DeleteCategoryUseCase:
    def __init__(self, uow: IContentUnitOfWork, bus: IEventBus) -> None:
        self._uow = uow
        self._bus = bus

    async def execute(
        self, cmd: DeleteCategoryCommand
    ) -> Result[None, DomainError]:
        category_id = CategoryId(cmd.category_public_id)
        async with self._uow as uow:
            category = await uow.categories.get(category_id)
            if category is None:
                return Err(CategoryNotFound(str(cmd.category_public_id)))
            await uow.categories.remove(category)
            await uow.commit()
            await self._bus.publish(
                CategoryDeleted(category_id=category.id.value, name=category.name)
            )
        return Ok(None)
