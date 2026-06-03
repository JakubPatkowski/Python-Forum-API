"""Value objects and enums for the ``files`` module.

All immutable, validated in ``__post_init__``. The aggregate (:mod:`file`)
composes these so invariants live in one place and cannot be bypassed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject

# A relaxed but safe MIME pattern: ``type/subtype`` with the usual token chars.
_MIME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*/[A-Za-z0-9][A-Za-z0-9.+-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Object keys we generate look like ``ab/cd/<uuid>.<ext>`` — keep them tame.
_STORAGE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/._-]{0,254}$")


class FileStatus(StrEnum):
    """Lifecycle of a file record.

    ``PENDING`` — a row exists and a presigned upload URL was handed out, but
    the bytes have not been validated/finalised yet.
    ``READY``   — bytes are in object storage, sniffed and (for images)
    thumbnailed; safe to serve.
    """

    PENDING = "pending"
    READY = "ready"


class FileOwnerType(StrEnum):
    """What a file is attached to.

    ``STANDALONE`` is the initial state straight after upload — the file has no
    owner yet and is an orphan candidate until attached (or cleaned up).
    """

    STANDALONE = "standalone"
    POST = "post"
    # Ikona/miniatura wątku — osobny typ od zwykłych załączników (POST), żeby nie
    # mieszać się z galerią załączników. Wskazuje na ten sam FK ``owner_post_id``.
    POST_ICON = "post_icon"
    COMMENT = "comment"
    USER_AVATAR = "user_avatar"
    CATEGORY = "category"


class FileKind(StrEnum):
    """Coarse media class derived from the MIME type.

    Drives presentation: images/videos/audio render inline, everything else
    is offered as a download.
    """

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class MimeType(ValueObject):
    """A validated ``type/subtype`` MIME string."""

    value: str

    def __post_init__(self) -> None:
        if not _MIME_RE.match(self.value):
            raise ValidationError(f"Invalid MIME type: {self.value!r}", field="content_type")

    @property
    def kind(self) -> FileKind:
        top = self.value.split("/", 1)[0].lower()
        match top:
            case "image":
                return FileKind.IMAGE
            case "video":
                return FileKind.VIDEO
            case "audio":
                return FileKind.AUDIO
            case _:
                return FileKind.DOCUMENT

    @property
    def is_image(self) -> bool:
        return self.kind is FileKind.IMAGE

    @property
    def renders_inline(self) -> bool:
        """Images, video and audio are shown inline; documents download."""
        return self.kind in (FileKind.IMAGE, FileKind.VIDEO, FileKind.AUDIO)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ByteSize(ValueObject):
    """A strictly-positive size in bytes."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError("File size must be positive", field="size_bytes")

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True, slots=True)
class Sha256(ValueObject):
    """A lowercase hex SHA-256 digest (64 chars)."""

    value: str

    def __post_init__(self) -> None:
        if not _SHA256_RE.match(self.value):
            raise ValidationError("Invalid SHA-256 digest", field="sha256")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class StorageKey(ValueObject):
    """Object key (path) of a file inside the storage bucket."""

    value: str

    def __post_init__(self) -> None:
        if not _STORAGE_KEY_RE.match(self.value):
            raise ValidationError("Invalid storage key", field="storage_key")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ImageVariant(ValueObject):
    """A generated thumbnail/resized rendition of an image file.

    ``name`` matches a key from ``settings.IMAGE_THUMBNAIL_SIZES`` (e.g.
    ``thumb``, ``medium``). The variant lives at its own ``storage_key``.
    """

    name: str
    storage_key: StorageKey
    width: int
    height: int
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("Variant name must be non-empty", field="variant")
        if self.width <= 0 or self.height <= 0:
            raise ValidationError("Variant dimensions must be positive", field="variant")
