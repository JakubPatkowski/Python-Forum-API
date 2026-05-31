"""Upload an image and set it as the caller's avatar (proxied + attach)."""

from __future__ import annotations

from app.modules.files.application.commands import FileView, SetAvatarCommand
from app.modules.files.application.errors import UnsupportedFileType
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
from app.modules.files.domain.events import AvatarChanged
from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import FileOwnerType
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class SetAvatarUseCase:
    """Replace the user's avatar with a freshly uploaded image.

    Avatars must be images. The previous avatar file (if any) is deleted so we
    never accumulate orphaned avatars.
    """

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

    async def execute(self, cmd: SetAvatarCommand) -> Result[FileView, DomainError]:
        try:
            declared = validate_declared_type(cmd.content_type)
            if not declared.is_image:
                raise UnsupportedFileType(declared.value)
            enforce_size(len(cmd.data))
        except DomainError as exc:
            return Err(exc)

        key = generate_storage_key(cmd.original_name)
        file = File.request_upload(
            uploader_id=UserId(cmd.user_public_id),
            storage_key=key,
            original_name=cmd.original_name,
            content_type=declared,
        )
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
        file.attach_to(
            owner_type=FileOwnerType.USER_AVATAR, owner_public_id=cmd.user_public_id
        )

        old_keys: tuple[str, ...] = ()
        async with self._uow as uow:
            old_public_id = await uow.current_avatar_file_public_id(cmd.user_public_id)

            await uow.files.add(file)
            internal_id = await uow.file_internal_id(file.id.value)
            await uow.set_user_avatar(cmd.user_public_id, internal_id)

            events = list(file.pull_events())
            if old_public_id is not None and old_public_id != file.id.value:
                old = await uow.files.get(FileId(old_public_id))
                if old is not None:
                    old_keys = old.all_storage_keys()
                    old.record_deletion()
                    await uow.files.remove(old)
                    events.extend(old.pull_events())

            await uow.commit()
            view = await build_file_view(file, storage=self._storage)

        if old_keys:
            await self._storage.remove_many(old_keys)
        events.append(AvatarChanged(user_id=cmd.user_public_id, file_id=file.id.value))
        for event in events:
            await self._bus.publish(event)
        return Ok(view)
