"""Read a single file's metadata + fresh presigned URLs."""

from __future__ import annotations

from uuid import UUID

from app.modules.files.application.commands import FileView
from app.modules.files.application.errors import FileNotFound, FileNotReady
from app.modules.files.application.file_processing import build_file_view
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.modules.files.domain.file import FileId
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class GetFileUseCase:
    """Return a :class:`FileView` for one file.

    Visibility: attached (READY) files are public, mirroring public posts.
    A standalone file is private to its uploader until it is attached.
    """

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def execute(
        self, file_public_id: UUID, *, actor_public_id: UUID | None = None
    ) -> Result[FileView, DomainError]:
        async with self._uow as uow:
            file = await uow.files.get(FileId(file_public_id))
            if file is None:
                return Err(FileNotFound(str(file_public_id)))
            if not file.is_ready:
                return Err(FileNotReady(str(file_public_id)))
            # Standalone files are only visible to their uploader.
            if not file.is_attached and file.uploader_id.value != actor_public_id:
                return Err(FileNotFound(str(file_public_id)))
            view = await build_file_view(file, storage=self._storage)
        return Ok(view)
