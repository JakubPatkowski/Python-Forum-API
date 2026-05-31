"""Step 2 of the presigned upload flow: validate the bytes and finalise."""

from __future__ import annotations

from app.modules.files.application.commands import CompleteUploadCommand, FileView
from app.modules.files.application.errors import (
    FileNotFound,
    UploadNotConfirmed,
)
from app.modules.files.application.file_processing import build_file_view, finalize_file
from app.modules.files.application.ports import (
    IFileProcessor,
    IFileStorage,
    IFilesUnitOfWork,
)
from app.modules.files.domain.file import FileId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError, PermissionDeniedError


class CompleteUploadUseCase:
    """Finalise a presigned upload: pull the object, sniff, hash, thumbnail."""

    def __init__(
        self,
        uow: IFilesUnitOfWork,
        storage: IFileStorage,
        processor: IFileProcessor,
        bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._processor = processor
        self._bus = bus

    async def execute(
        self, cmd: CompleteUploadCommand
    ) -> Result[FileView, DomainError]:
        async with self._uow as uow:
            file = await uow.files.get(FileId(cmd.file_public_id))
            if file is None:
                return Err(FileNotFound(str(cmd.file_public_id)))
            if file.uploader_id.value != cmd.actor_public_id:
                return Err(PermissionDeniedError("Not your upload"))

            # Idempotent: re-completing an already-ready file just returns it.
            if file.is_ready:
                view = await build_file_view(file, storage=self._storage)
                return Ok(view)

            stat = await self._storage.stat(str(file.storage_key))
            if stat is None:
                return Err(UploadNotConfirmed(str(cmd.file_public_id)))

            data = await self._storage.get_bytes(str(file.storage_key))
            try:
                await finalize_file(
                    file,
                    data,
                    declared=file.content_type,
                    processor=self._processor,
                    storage=self._storage,
                )
            except DomainError as exc:
                # Reject bad bytes: purge the object so it cannot be served.
                await self._storage.remove_many(file.all_storage_keys())
                await uow.files.remove(file)
                await uow.commit()
                return Err(exc)

            await uow.files.save(file)
            await uow.commit()
            events = file.pull_events()
            view = await build_file_view(file, storage=self._storage)

        for event in events:
            await self._bus.publish(event)
        return Ok(view)
