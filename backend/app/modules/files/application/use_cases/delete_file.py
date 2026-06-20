"""Delete a file: remove the DB row and purge all objects from storage."""

from __future__ import annotations

from app.modules.files.application.commands import DeleteFileCommand
from app.modules.files.application.errors import FileNotFound
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.modules.files.domain.file import FileId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError, PermissionDeniedError


class DeleteFileUseCase:
    """Remove a file. Allowed for the uploader or ``file.delete.any`` holders.

    The DB FK ``users.avatar_file_id`` is ``ON DELETE SET NULL``, so deleting a
    file that happens to be an avatar clears the avatar automatically.
    """

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage, bus: IEventBus) -> None:
        self._uow = uow
        self._storage = storage
        self._bus = bus

    async def execute(self, cmd: DeleteFileCommand) -> Result[None, DomainError]:
        async with self._uow as uow:
            file = await uow.files.get(FileId(cmd.file_public_id))
            if file is None:
                return Err(FileNotFound(str(cmd.file_public_id)))
            if file.uploader_id.value != cmd.actor_public_id and not cmd.actor_can_delete_any:
                return Err(PermissionDeniedError("Not your file"))

            keys = file.all_storage_keys()
            file.record_deletion()
            await uow.files.remove(file)
            await uow.commit()
            events = file.pull_events()

        await self._storage.remove_many(keys)
        for event in events:
            await self._bus.publish(event)
        return Ok(None)
