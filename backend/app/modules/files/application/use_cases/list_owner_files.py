"""List all files attached to a given owner (post / comment / category)."""

from __future__ import annotations

from app.modules.files.application.commands import FileView, ListOwnerFilesQuery
from app.modules.files.application.file_processing import build_file_view
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.shared.application.result import Ok, Result
from app.shared.domain.errors import DomainError


class ListOwnerFilesUseCase:
    """Return the public attachment list for an owner (used to render galleries)."""

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def execute(
        self, query: ListOwnerFilesQuery
    ) -> Result[list[FileView], DomainError]:
        async with self._uow as uow:
            files = await uow.files.list_for_owner(
                query.owner_type, query.owner_public_id
            )
            views = [await build_file_view(f, storage=self._storage) for f in files]
        return Ok(views)
