"""List every category alphabetically."""

from __future__ import annotations

from app.shared.application.result import Ok, Result
from app.shared.domain.errors import DomainError

from app.modules.content.application.commands import CategorySummary
from app.modules.content.application.ports import IContentUnitOfWork


class ListCategoriesUseCase:
    def __init__(self, uow: IContentUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> Result[list[CategorySummary], DomainError]:
        async with self._uow as uow:
            return Ok(await uow.categories.list_all())
