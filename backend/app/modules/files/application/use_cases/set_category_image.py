"""Upload an image and set it as a category's image (moderators)."""

from __future__ import annotations

from app.modules.files.application.commands import FileView, SetCategoryImageCommand
from app.modules.files.application.errors import OwnerNotFound, UnsupportedFileType
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
from app.modules.files.domain.events import CategoryImageChanged
from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import FileOwnerType
from app.modules.identity.domain.user import UserId
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError


class SetCategoryImageUseCase:
    """Replace a category's image. Permission (``category.manage``) is enforced
    in the router; the previous image file is deleted to avoid orphans."""

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
        self, cmd: SetCategoryImageCommand
    ) -> Result[FileView, DomainError]:
        try:
            declared = validate_declared_type(cmd.content_type)
            if not declared.is_image:
                raise UnsupportedFileType(declared.value)
            enforce_size(len(cmd.data))
        except DomainError as exc:
            return Err(exc)

        async with self._uow as uow:
            if not await uow.category_exists(cmd.category_public_id):
                return Err(OwnerNotFound("category", str(cmd.category_public_id)))

        key = generate_storage_key(cmd.original_name)
        file = File.request_upload(
            uploader_id=UserId(cmd.actor_public_id),
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
            owner_type=FileOwnerType.CATEGORY, owner_public_id=cmd.category_public_id
        )

        old_keys: tuple[str, ...] = ()
        async with self._uow as uow:
            old_public_id = await uow.current_category_image_file_public_id(
                cmd.category_public_id
            )
            await uow.files.add(file)
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
        events.append(
            CategoryImageChanged(
                category_id=cmd.category_public_id, file_id=file.id.value
            )
        )
        for event in events:
            await self._bus.publish(event)
        return Ok(view)
