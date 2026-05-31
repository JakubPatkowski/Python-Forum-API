"""Resolve the single 'primary image' of a user (avatar) or category.

Used by the redirect endpoints ``GET /users/{id}/avatar`` and
``GET /categories/{id}/image`` to send the browser straight to MinIO.
"""

from __future__ import annotations

from uuid import UUID

from app.modules.files.application.commands import FileView
from app.modules.files.application.file_processing import build_file_view
from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.modules.files.domain.file import FileId
from app.shared.application.result import Ok, Result
from app.shared.domain.errors import DomainError


class GetAvatarUseCase:
    """Return the user's current avatar as a :class:`FileView`, or ``None``."""

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def execute(
        self, user_public_id: UUID
    ) -> Result[FileView | None, DomainError]:
        async with self._uow as uow:
            public_id = await uow.current_avatar_file_public_id(user_public_id)
            if public_id is None:
                return Ok(None)
            file = await uow.files.get(FileId(public_id))
            if file is None or not file.is_ready:
                return Ok(None)
            return Ok(await build_file_view(file, storage=self._storage))


class GetCategoryImageUseCase:
    """Return the category's current image as a :class:`FileView`, or ``None``."""

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def execute(
        self, category_public_id: UUID
    ) -> Result[FileView | None, DomainError]:
        async with self._uow as uow:
            public_id = await uow.current_category_image_file_public_id(
                category_public_id
            )
            if public_id is None:
                return Ok(None)
            file = await uow.files.get(FileId(public_id))
            if file is None or not file.is_ready:
                return Ok(None)
            return Ok(await build_file_view(file, storage=self._storage))
