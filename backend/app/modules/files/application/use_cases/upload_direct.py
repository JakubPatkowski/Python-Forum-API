"""Proxied upload: stream bytes through the backend to MinIO in one request.

Convenience/fallback path (avatars, tests, small files, clients that cannot
reach MinIO directly). The performant path is the presigned flow.
"""

from __future__ import annotations

from app.modules.files.application.commands import DirectUploadCommand, FileView
from app.modules.files.application.file_processing import (
    build_file_view,
    enforce_size,
    finalize_file,
    generate_storage_key,
    validate_declared_type,
)
from app.modules.files.application.ports import (
    IFileProcessor,
    IFileStorage,
    IFilesUnitOfWork,
)
from app.modules.files.domain.file import File
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class DirectUploadUseCase:
    """Validate + store bytes + finalise a file in a single call."""

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

    async def execute(self, cmd: DirectUploadCommand) -> Result[FileView, DomainError]:
        try:
            declared = validate_declared_type(cmd.content_type)
            enforce_size(len(cmd.data))
        except DomainError as exc:
            return Err(exc)

        key = generate_storage_key(cmd.original_name)
        file = File.request_upload(
            uploader_id=UserId(cmd.uploader_public_id),
            storage_key=key,
            original_name=cmd.original_name,
            content_type=declared,
        )

        # Upload the original bytes first, then validate + thumbnail.
        await self._storage.put_bytes(str(key), cmd.data, content_type=declared.value)
        try:
            await finalize_file(
                file,
                cmd.data,
                declared=declared,
                processor=self._processor,
                storage=self._storage,
            )
        except DomainError as exc:
            await self._storage.remove_many(file.all_storage_keys())
            return Err(exc)

        async with self._uow as uow:
            await uow.files.add(file)
            await uow.commit()
            events = file.pull_events()
            view = await build_file_view(file, storage=self._storage)

        for event in events:
            await self._bus.publish(event)
        return Ok(view)
