"""File aggregate root.

A ``File`` is the single, generic representation of every uploaded byte
stream in the system — post/comment attachments, user avatars and category
images alike. It owns only *metadata*; the bytes live in object storage
(MinIO) addressed by :class:`StorageKey`.

Lifecycle::

    request_upload()  ->  PENDING   (presigned PUT URL handed to the client)
    mark_ready()      ->  READY     (bytes validated, thumbnails generated)
    attach_to()       ->  owner set (post / comment / avatar / category)
    detach()          ->  STANDALONE again

A freshly uploaded file is ``STANDALONE`` and counts as an orphan until it is
attached; the cleanup job removes standalone files older than the retention
window.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.files.domain.events import (
    FileAttached,
    FileDeleted,
    FileDetached,
    FileUploaded,
)
from app.modules.files.domain.value_objects import (
    ByteSize,
    FileKind,
    FileOwnerType,
    FileStatus,
    ImageVariant,
    MimeType,
    Sha256,
    StorageKey,
)

# Referenced by UUID only — files never import the User aggregate, keeping the
# modules independent (same convention as content -> identity).
from app.modules.identity.domain.user import UserId
from app.shared.domain.entity import AggregateRoot
from app.shared.domain.entity_id import EntityId
from app.shared.domain.errors import ConflictError, ValidationError

_NAME_MAX = 255


class FileId(EntityId["File"]):
    """Public identifier (UUID) of a :class:`File`."""


class File(AggregateRoot[FileId]):
    """Aggregate root for a single stored file and its metadata."""

    def __init__(
        self,
        *,
        id: FileId,
        uploader_id: UserId,
        storage_key: StorageKey,
        original_name: str,
        content_type: MimeType,
        status: FileStatus = FileStatus.PENDING,
        size_bytes: int = 0,
        sha256: Sha256 | None = None,
        owner_type: FileOwnerType = FileOwnerType.STANDALONE,
        owner_id: UUID | None = None,
        width: int | None = None,
        height: int | None = None,
        variants: dict[str, ImageVariant] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self._uploader_id = uploader_id
        self._storage_key = storage_key
        self._original_name = self._clean_name(original_name)
        self._content_type = content_type
        self._status = status
        self._size_bytes = size_bytes
        self._sha256 = sha256
        self._owner_type = owner_type
        self._owner_id = owner_id
        self._width = width
        self._height = height
        self._variants: dict[str, ImageVariant] = dict(variants or {})
        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    # --- read-only accessors ------------------------------------------------

    @property
    def uploader_id(self) -> UserId:
        return self._uploader_id

    @property
    def storage_key(self) -> StorageKey:
        return self._storage_key

    @property
    def original_name(self) -> str:
        return self._original_name

    @property
    def content_type(self) -> MimeType:
        return self._content_type

    @property
    def status(self) -> FileStatus:
        return self._status

    @property
    def size_bytes(self) -> int:
        return self._size_bytes

    @property
    def sha256(self) -> Sha256 | None:
        return self._sha256

    @property
    def owner_type(self) -> FileOwnerType:
        return self._owner_type

    @property
    def owner_id(self) -> UUID | None:
        return self._owner_id

    @property
    def width(self) -> int | None:
        return self._width

    @property
    def height(self) -> int | None:
        return self._height

    @property
    def variants(self) -> dict[str, ImageVariant]:
        return dict(self._variants)

    @property
    def kind(self) -> FileKind:
        return self._content_type.kind

    @property
    def is_ready(self) -> bool:
        return self._status is FileStatus.READY

    @property
    def is_attached(self) -> bool:
        return self._owner_type is not FileOwnerType.STANDALONE

    @property
    def renders_inline(self) -> bool:
        return self._content_type.renders_inline

    def default_disposition(self) -> str:
        """``inline`` for media, ``attachment`` for documents."""
        return "inline" if self.renders_inline else "attachment"

    def all_storage_keys(self) -> tuple[str, ...]:
        """Every object key owned by this file: original + all variants."""
        return (str(self._storage_key), *(str(v.storage_key) for v in self._variants.values()))

    # --- factories ----------------------------------------------------------

    @classmethod
    def request_upload(
        cls,
        *,
        uploader_id: UserId,
        storage_key: StorageKey,
        original_name: str,
        content_type: MimeType,
    ) -> File:
        """Create a PENDING file before its bytes exist.

        Used by both the presigned flow (client will PUT to ``storage_key``)
        and the proxied flow (server streams to ``storage_key`` then finalises).
        """
        return cls(
            id=FileId.new(),
            uploader_id=uploader_id,
            storage_key=storage_key,
            original_name=original_name,
            content_type=content_type,
            status=FileStatus.PENDING,
        )

    # --- mutations ----------------------------------------------------------

    def mark_ready(
        self,
        *,
        size_bytes: int,
        sha256: Sha256,
        content_type: MimeType | None = None,
        width: int | None = None,
        height: int | None = None,
        variants: dict[str, ImageVariant] | None = None,
    ) -> None:
        """Finalise the upload: validated bytes are now in storage.

        Raises :class:`ConflictError` if the file was already finalised so a
        duplicate ``complete`` call cannot silently overwrite metadata.
        """
        if self._status is FileStatus.READY:
            raise ConflictError("File already finalised", field="status")
        ByteSize(size_bytes)  # validate > 0
        self._size_bytes = size_bytes
        self._sha256 = sha256
        if content_type is not None:
            self._content_type = content_type
        self._width = width
        self._height = height
        self._variants = dict(variants or {})
        self._status = FileStatus.READY
        self._touch()
        self.record_event(
            FileUploaded(
                file_id=self.id.value,
                uploader_id=self._uploader_id.value,
                storage_key=str(self._storage_key),
                content_type=str(self._content_type),
                size_bytes=size_bytes,
            )
        )

    def attach_to(self, *, owner_type: FileOwnerType, owner_public_id: UUID) -> None:
        """Bind this file to an owner. The file must be READY."""
        if owner_type is FileOwnerType.STANDALONE:
            raise ValidationError("Cannot attach to STANDALONE owner", field="owner_type")
        if not self.is_ready:
            raise ConflictError("Cannot attach a file that is not ready", field="status")
        self._owner_type = owner_type
        self._owner_id = owner_public_id
        self._touch()
        self.record_event(
            FileAttached(
                file_id=self.id.value,
                owner_type=owner_type.value,
                owner_public_id=owner_public_id,
            )
        )

    def detach(self) -> None:
        """Unbind from the current owner; becomes STANDALONE (orphan) again."""
        if not self.is_attached:
            return
        self._owner_type = FileOwnerType.STANDALONE
        self._owner_id = None
        self._touch()
        self.record_event(FileDetached(file_id=self.id.value))

    def record_deletion(self) -> None:
        """Record a :class:`FileDeleted` event carrying the keys to purge.

        Call right before the repository removes the row; the use case then
        deletes the objects from storage after the commit.
        """
        self.record_event(
            FileDeleted(
                file_id=self.id.value,
                storage_key=str(self._storage_key),
                variant_keys=tuple(str(v.storage_key) for v in self._variants.values()),
            )
        )

    # --- helpers ------------------------------------------------------------

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = (name or "").strip().replace("\n", " ").replace("\r", " ")
        if not cleaned:
            raise ValidationError("Original file name is required", field="original_name")
        return cleaned[:_NAME_MAX]
