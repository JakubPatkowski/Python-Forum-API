"""SQLAlchemy implementation of :class:`IFileRepository`.

Owner/uploader ids cross module boundaries: the aggregate speaks public UUIDs,
the table stores the legacy integer FKs. The UoW injects sync resolver
callables (mirroring the content repositories) so this class stays SQL-light.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User as UserOrm
from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import FileOwnerType, FileStatus
from app.modules.files.infrastructure.mappers import file_from_orm, variants_to_json
from app.modules.files.infrastructure.orm import FileOrm

_Resolver = Callable[[UUID], int | None]


class SqlAlchemyFileRepository:
    """Persists :class:`File` aggregates in the ``files`` table."""

    def __init__(
        self,
        session: Session,
        *,
        user_id_resolver: _Resolver,
        post_id_resolver: _Resolver,
        comment_id_resolver: _Resolver,
        category_id_resolver: _Resolver,
    ) -> None:
        self._s = session
        self._resolve_user = user_id_resolver
        self._resolve_post = post_id_resolver
        self._resolve_comment = comment_id_resolver
        self._resolve_category = category_id_resolver

    # --- reads --------------------------------------------------------------

    async def get(self, id_: FileId) -> File | None:
        row = self._s.execute(
            select(FileOrm, UserOrm.public_id)
            .join(UserOrm, FileOrm.uploader_id == UserOrm.id)
            .where(FileOrm.public_id == id_.value)
        ).first()
        if row is None:
            return None
        orm, uploader_public_id = row
        return file_from_orm(orm, uploader_public_id=uploader_public_id)

    async def exists(self, id_: FileId) -> bool:
        return (
            self._s.scalar(
                select(FileOrm.id).where(FileOrm.public_id == id_.value)
            )
            is not None
        )

    async def list_for_owner(
        self, owner_type: FileOwnerType, owner_public_id: UUID
    ) -> list[File]:
        owner_col = self._owner_column_for(owner_type)
        owner_internal = self._resolve_owner_internal(owner_type, owner_public_id)
        if owner_col is None or owner_internal is None:
            return []
        rows = self._s.execute(
            select(FileOrm, UserOrm.public_id)
            .join(UserOrm, FileOrm.uploader_id == UserOrm.id)
            .where(
                FileOrm.owner_type == owner_type,
                owner_col == owner_internal,
                FileOrm.status == FileStatus.READY,
            )
            .order_by(FileOrm.created_at.asc())
        ).all()
        return [
            file_from_orm(
                orm, uploader_public_id=up, owner_public_id=owner_public_id
            )
            for orm, up in rows
        ]

    async def list_by_uploader(
        self, uploader_public_id: UUID, *, limit: int, offset: int
    ) -> list[File]:
        internal = self._resolve_user(uploader_public_id)
        if internal is None:
            return []
        rows = self._s.execute(
            select(FileOrm, UserOrm.public_id)
            .join(UserOrm, FileOrm.uploader_id == UserOrm.id)
            .where(
                FileOrm.uploader_id == internal,
                FileOrm.status == FileStatus.READY,
            )
            .order_by(FileOrm.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [file_from_orm(orm, uploader_public_id=up) for orm, up in rows]

    async def list_orphans(
        self, *, older_than: datetime, limit: int
    ) -> list[File]:
        rows = self._s.execute(
            select(FileOrm, UserOrm.public_id)
            .join(UserOrm, FileOrm.uploader_id == UserOrm.id)
            .where(
                FileOrm.owner_type == FileOwnerType.STANDALONE,
                FileOrm.created_at < older_than,
            )
            .order_by(FileOrm.created_at.asc())
            .limit(limit)
        ).all()
        return [file_from_orm(orm, uploader_public_id=up) for orm, up in rows]

    # --- writes -------------------------------------------------------------

    async def add(self, entity: File) -> None:
        uploader_internal = self._resolve_user(entity.uploader_id.value)
        if uploader_internal is None:
            msg = f"Unknown uploader {entity.uploader_id.value}"
            raise ValueError(msg)
        post_id, comment_id, user_id, category_id = self._owner_ints(entity)
        row = FileOrm(
            public_id=entity.id.value,
            uploader_id=uploader_internal,
            storage_key=str(entity.storage_key),
            original_name=entity.original_name,
            content_type=str(entity.content_type),
            size_bytes=entity.size_bytes,
            sha256=str(entity.sha256) if entity.sha256 else None,
            status=entity.status,
            owner_type=entity.owner_type,
            owner_post_id=post_id,
            owner_comment_id=comment_id,
            owner_user_id=user_id,
            owner_category_id=category_id,
            width=entity.width,
            height=entity.height,
            variants=variants_to_json(entity.variants) or None,
        )
        self._s.add(row)
        self._s.flush()  # assign files.id so the avatar FK lookup can see it

    async def save(self, file: File) -> None:
        row = self._s.scalar(
            select(FileOrm).where(FileOrm.public_id == file.id.value)
        )
        if row is None:
            msg = f"File {file.id.value} not found for update"
            raise ValueError(msg)
        post_id, comment_id, user_id, category_id = self._owner_ints(file)
        row.storage_key = str(file.storage_key)
        row.original_name = file.original_name
        row.content_type = str(file.content_type)
        row.size_bytes = file.size_bytes
        row.sha256 = str(file.sha256) if file.sha256 else None
        row.status = file.status
        row.owner_type = file.owner_type
        row.owner_post_id = post_id
        row.owner_comment_id = comment_id
        row.owner_user_id = user_id
        row.owner_category_id = category_id
        row.width = file.width
        row.height = file.height
        row.variants = variants_to_json(file.variants) or None
        self._s.flush()

    async def remove(self, entity: File) -> None:
        row = self._s.scalar(
            select(FileOrm).where(FileOrm.public_id == entity.id.value)
        )
        if row is not None:
            self._s.delete(row)
            self._s.flush()

    # --- helpers ------------------------------------------------------------

    def _owner_column_for(self, owner_type: FileOwnerType):
        return {
            FileOwnerType.POST: FileOrm.owner_post_id,
            # Ikona wątku korzysta z tej samej kolumny FK co załączniki posta.
            FileOwnerType.POST_ICON: FileOrm.owner_post_id,
            FileOwnerType.COMMENT: FileOrm.owner_comment_id,
            FileOwnerType.USER_AVATAR: FileOrm.owner_user_id,
            FileOwnerType.CATEGORY: FileOrm.owner_category_id,
        }.get(owner_type)

    def _resolve_owner_internal(
        self, owner_type: FileOwnerType, owner_public_id: UUID
    ) -> int | None:
        match owner_type:
            case FileOwnerType.POST | FileOwnerType.POST_ICON:
                return self._resolve_post(owner_public_id)
            case FileOwnerType.COMMENT:
                return self._resolve_comment(owner_public_id)
            case FileOwnerType.USER_AVATAR:
                return self._resolve_user(owner_public_id)
            case FileOwnerType.CATEGORY:
                return self._resolve_category(owner_public_id)
            case _:
                return None

    def _owner_ints(
        self, file: File
    ) -> tuple[int | None, int | None, int | None, int | None]:
        """Map the aggregate's owner to the four nullable FK columns."""
        if file.owner_id is None or file.owner_type is FileOwnerType.STANDALONE:
            return (None, None, None, None)
        internal = self._resolve_owner_internal(file.owner_type, file.owner_id)
        post_types = (FileOwnerType.POST, FileOwnerType.POST_ICON)
        return (
            internal if file.owner_type in post_types else None,
            internal if file.owner_type is FileOwnerType.COMMENT else None,
            internal if file.owner_type is FileOwnerType.USER_AVATAR else None,
            internal if file.owner_type is FileOwnerType.CATEGORY else None,
        )
