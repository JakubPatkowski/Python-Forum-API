"""Ports consumed by the files use cases.

* :class:`IFileStorage`     — object storage (MinIO/S3) abstraction.
* :class:`IFileRepository`  — persistence of file metadata.
* :class:`IFilesUnitOfWork` — transaction + cross-module id resolvers.

The application layer depends only on these protocols; concrete adapters
(minio-py, SQLAlchemy) live in ``infrastructure``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import FileOwnerType
from app.shared.application.repository import IRepository

# --------------------------------------------------------------------------- #
# Object storage                                                              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ObjectStat:
    """Minimal metadata of an object that exists in the bucket."""

    size_bytes: int
    content_type: str | None


class IFileStorage(Protocol):
    """S3-compatible object storage (MinIO). All bytes live here, not in DB."""

    async def ensure_bucket(self) -> None:
        """Create the configured bucket if it does not exist (idempotent)."""

    async def presigned_put_url(
        self, key: str, *, content_type: str, expires_seconds: int
    ) -> str:
        """A time-limited URL the browser uses to PUT bytes straight to MinIO."""

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        disposition: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """A time-limited URL to GET an object directly from MinIO.

        ``disposition`` (``inline``/``attachment``) and ``filename`` are baked
        into ``response-content-disposition`` so the browser behaves correctly.
        """

    async def put_bytes(self, key: str, data: bytes, *, content_type: str) -> None:
        """Upload bytes (server-side: avatars, thumbnails, proxied uploads)."""

    async def get_bytes(self, key: str) -> bytes:
        """Download an object's bytes (for sniffing / thumbnailing at finalise)."""

    async def stat(self, key: str) -> ObjectStat | None:
        """Return object metadata, or ``None`` if it does not exist."""

    async def remove(self, key: str) -> None:
        """Delete one object (idempotent — missing is not an error)."""

    async def remove_many(self, keys: Iterable[str]) -> None:
        """Delete several objects (original + thumbnails) in one call."""


# --------------------------------------------------------------------------- #
# Content inspection / image processing                                       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ProcessedVariant:
    """A generated thumbnail ready to be stored."""

    name: str
    data: bytes
    width: int
    height: int
    content_type: str


class IFileProcessor(Protocol):
    """MIME sniffing + image thumbnail generation (libmagic + Pillow)."""

    def sniff_mime(self, data: bytes) -> str:
        """Detect the real MIME type from the bytes (never trust the client)."""

    def probe_image(self, data: bytes) -> tuple[int, int] | None:
        """Return ``(width, height)`` for an image, else ``None``."""

    def make_image_variants(
        self, data: bytes, *, sizes: dict[str, int]
    ) -> list[ProcessedVariant]:
        """Generate downscaled renditions; only sizes smaller than the source."""


# --------------------------------------------------------------------------- #
# Repository                                                                  #
# --------------------------------------------------------------------------- #


class IFileRepository(IRepository[File, FileId], Protocol):
    """Persistence port for :class:`File` aggregates."""

    async def save(self, file: File) -> None:
        """Persist mutations on an already-loaded file (status, owner, …)."""

    async def list_for_owner(
        self, owner_type: FileOwnerType, owner_public_id: UUID
    ) -> list[File]:
        """All READY files attached to a given owner, oldest first."""

    async def list_by_uploader(
        self, uploader_public_id: UUID, *, limit: int, offset: int
    ) -> list[File]:
        """The uploader's own files (a lightweight 'my uploads' gallery)."""

    async def list_orphans(self, *, older_than: datetime, limit: int) -> list[File]:
        """Standalone files created before ``older_than`` (cleanup candidates)."""


# --------------------------------------------------------------------------- #
# Unit of Work                                                                #
# --------------------------------------------------------------------------- #


class IFilesUnitOfWork(Protocol):
    """Transactional scope for the files repository plus cross-module lookups.

    Like the content UoW, this reaches into the legacy integer FKs of other
    modules (``users``/``posts``/``comments``/``categories``) through small
    resolver helpers, so use cases stay free of SQL.
    """

    files: IFileRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    # --- cross-module resolvers --------------------------------------------

    async def resolve_user_id(self, user_public_id: UUID) -> int | None:
        """Translate a user UUID into ``users.id`` (None if absent)."""

    async def file_internal_id(self, file_public_id: UUID) -> int | None:
        """Translate a file UUID into ``files.id`` (used for avatar/category FKs)."""

    async def get_post_author(self, post_public_id: UUID) -> UUID | None:
        """Author's public id for a post, or None if the post does not exist."""

    async def get_comment_author(self, comment_public_id: UUID) -> UUID | None:
        """Author's public id for a comment, or None if it does not exist."""

    async def category_exists(self, category_public_id: UUID) -> bool: ...

    # --- avatar / category image FKs ---------------------------------------

    async def set_user_avatar(
        self, user_public_id: UUID, file_internal_id: int | None
    ) -> None:
        """Point ``users.avatar_file_id`` at a file (or clear it with None)."""

    async def current_avatar_file_public_id(
        self, user_public_id: UUID
    ) -> UUID | None:
        """Public id of the user's current avatar file, if any."""

    async def current_category_image_file_public_id(
        self, category_public_id: UUID
    ) -> UUID | None:
        """Public id of a category's current image file, if any."""

    async def current_post_icon_file_public_id(
        self, post_public_id: UUID
    ) -> UUID | None:
        """Public id of a post's current icon file, if any."""
