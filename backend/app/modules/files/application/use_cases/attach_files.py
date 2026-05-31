"""Attach already-uploaded standalone files to an owner.

This is the join point with the content module. The flow the user described —
upload first (get an id), then reference that id when creating a post — is
realised here: the post/comment is created normally, then its file ids are
attached through this use case.
"""

from __future__ import annotations

from app.modules.files.application.commands import AttachFilesCommand, FileView
from app.modules.files.application.errors import (
    FileNotFound,
    FileNotReady,
    OwnerNotFound,
)
from app.modules.files.application.file_processing import build_file_view
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.modules.files.domain.file import FileId
from app.modules.files.domain.value_objects import FileOwnerType
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import DomainError, PermissionDeniedError


class AttachFilesUseCase:
    """Attach one or more files to a post, comment or category."""

    def __init__(
        self, uow: IFilesUnitOfWork, storage: IFileStorage, bus: IEventBus
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._bus = bus

    async def execute(
        self, cmd: AttachFilesCommand
    ) -> Result[list[FileView], DomainError]:
        async with self._uow as uow:
            authz = await self._authorize_owner(uow, cmd)
            if authz is not None:
                return Err(authz)

            attached = []
            for fid in cmd.file_ids:
                file = await uow.files.get(FileId(fid))
                if file is None:
                    return Err(FileNotFound(str(fid)))
                if not file.is_ready:
                    return Err(FileNotReady(str(fid)))
                if (
                    file.uploader_id.value != cmd.actor_public_id
                    and not cmd.actor_can_moderate
                ):
                    return Err(PermissionDeniedError("Not your file"))
                file.attach_to(
                    owner_type=cmd.owner_type, owner_public_id=cmd.owner_public_id
                )
                await uow.files.save(file)
                attached.append(file)

            await uow.commit()
            events = [e for f in attached for e in f.pull_events()]
            views = [await build_file_view(f, storage=self._storage) for f in attached]

        for event in events:
            await self._bus.publish(event)
        return Ok(views)

    async def _authorize_owner(
        self, uow: IFilesUnitOfWork, cmd: AttachFilesCommand
    ) -> DomainError | None:
        """Confirm the owner exists and the actor may attach to it."""
        match cmd.owner_type:
            case FileOwnerType.POST:
                author = await uow.get_post_author(cmd.owner_public_id)
                if author is None:
                    return OwnerNotFound("post", str(cmd.owner_public_id))
                if author != cmd.actor_public_id and not cmd.actor_can_moderate:
                    return PermissionDeniedError("Not the post author")
            case FileOwnerType.COMMENT:
                author = await uow.get_comment_author(cmd.owner_public_id)
                if author is None:
                    return OwnerNotFound("comment", str(cmd.owner_public_id))
                if author != cmd.actor_public_id and not cmd.actor_can_moderate:
                    return PermissionDeniedError("Not the comment author")
            case FileOwnerType.CATEGORY:
                if not cmd.actor_can_moderate:
                    return PermissionDeniedError("Category images require moderation")
                if not await uow.category_exists(cmd.owner_public_id):
                    return OwnerNotFound("category", str(cmd.owner_public_id))
            case _:
                return PermissionDeniedError(
                    "Use the avatar endpoint for avatars; standalone is not an owner"
                )
        return None
