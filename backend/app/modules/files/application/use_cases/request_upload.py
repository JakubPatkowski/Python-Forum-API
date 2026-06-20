"""Step 1 of the presigned upload flow: hand out a PUT URL."""

from __future__ import annotations

from app.config import settings
from app.modules.files.application.commands import RequestUploadCommand, UploadTicket
from app.modules.files.application.file_processing import (
    enforce_size,
    generate_storage_key,
    validate_declared_type,
)
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.modules.files.domain.file import File
from app.modules.identity.domain.user import UserId
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class RequestUploadUseCase:
    """Create a PENDING file and return a presigned PUT URL for MinIO.

    The browser then uploads bytes directly to MinIO (no backend round-trip),
    and calls ``complete`` to finalise.
    """

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def execute(self, cmd: RequestUploadCommand) -> Result[UploadTicket, DomainError]:
        try:
            declared = validate_declared_type(cmd.content_type)
            enforce_size(cmd.size_bytes)
        except DomainError as exc:
            return Err(exc)

        key = generate_storage_key(cmd.original_name)
        file = File.request_upload(
            uploader_id=UserId(cmd.uploader_public_id),
            storage_key=key,
            original_name=cmd.original_name,
            content_type=declared,
        )

        async with self._uow as uow:
            await uow.files.add(file)
            await uow.commit()

        upload_url = await self._storage.presigned_put_url(
            str(key),
            content_type=declared.value,
            expires_seconds=settings.FILE_UPLOAD_URL_TTL_SECONDS,
        )
        return Ok(
            UploadTicket(
                file_id=file.id.value,
                storage_key=str(key),
                upload_url=upload_url,
                method="PUT",
                expires_in_seconds=settings.FILE_UPLOAD_URL_TTL_SECONDS,
                max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
            )
        )
