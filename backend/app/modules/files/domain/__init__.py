"""Files domain: the :class:`File` aggregate, its value objects and events."""

from app.modules.files.domain.events import (
    AvatarChanged,
    CategoryImageChanged,
    FileAttached,
    FileDeleted,
    FileDetached,
    FileUploaded,
)
from app.modules.files.domain.file import File, FileId
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

__all__ = [
    "AvatarChanged",
    "ByteSize",
    "CategoryImageChanged",
    "File",
    "FileAttached",
    "FileDeleted",
    "FileDetached",
    "FileId",
    "FileKind",
    "FileOwnerType",
    "FileStatus",
    "FileUploaded",
    "ImageVariant",
    "MimeType",
    "Sha256",
    "StorageKey",
]
