"""List the caller's own uploaded files — a lightweight reuse 'gallery'."""

from __future__ import annotations

from app.modules.files.application.commands import FileView, ListMyFilesQuery
from app.modules.files.application.file_processing import build_file_view
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.shared.application.result import Ok, Result
from app.shared.domain.errors import DomainError


class ListMyFilesUseCase:
    """Return the uploader's recent files so they can be picked and re-used.

    This is the pragmatic answer to 'do we need a media gallery?': instead of a
    full media library, the user simply sees what they uploaded recently and
    can attach an existing file by id rather than re-uploading.
    """

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def execute(
        self, query: ListMyFilesQuery
    ) -> Result[list[FileView], DomainError]:
        async with self._uow as uow:
            files = await uow.files.list_by_uploader(
                query.uploader_public_id,
                limit=query.limit,
                offset=query.offset,
            )
            views = [await build_file_view(f, storage=self._storage) for f in files]
        return Ok(views)
