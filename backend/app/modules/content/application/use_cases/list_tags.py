"""List every tag known to the system (alphabetical)."""

from __future__ import annotations

from app.modules.content.application.commands import TagSummary
from app.modules.content.application.ports import IContentUnitOfWork
from app.shared.application.result import Ok, Result
from app.shared.domain.errors import DomainError


class ListTagsUseCase:
    def __init__(self, uow: IContentUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> Result[list[TagSummary], DomainError]:
        async with self._uow as uow:
            tags = await uow.tags.list_all()
        return Ok(
            [
                TagSummary(
                    public_id=t.id.value, name=t.name, slug=str(t.slug)
                )
                for t in tags
            ]
        )
