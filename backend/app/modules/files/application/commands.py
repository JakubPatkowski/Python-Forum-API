"""Commands, queries and read-model projections for the files module.

Commands/queries are the typed inputs to use cases. ``FileView`` /
``UploadTicket`` are the projections returned to the presentation layer
(already carrying freshly-minted presigned URLs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.modules.files.domain.value_objects import FileKind, FileOwnerType

# --------------------------------------------------------------------------- #
# Commands / queries                                                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RequestUploadCommand:
    """Start a presigned upload (step 1 of 2)."""

    uploader_public_id: UUID
    original_name: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class CompleteUploadCommand:
    """Finalise a presigned upload after the client PUT the bytes (step 2)."""

    file_public_id: UUID
    actor_public_id: UUID


@dataclass(frozen=True, slots=True)
class DirectUploadCommand:
    """Upload bytes through the backend in one request (proxied fallback)."""

    uploader_public_id: UUID
    original_name: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class AttachFilesCommand:
    """Attach one or more standalone files to an owner."""

    actor_public_id: UUID
    owner_type: FileOwnerType
    owner_public_id: UUID
    file_ids: tuple[UUID, ...]
    actor_can_moderate: bool = False


@dataclass(frozen=True, slots=True)
class DeleteFileCommand:
    file_public_id: UUID
    actor_public_id: UUID
    actor_can_delete_any: bool = False


@dataclass(frozen=True, slots=True)
class SetAvatarCommand:
    """Upload an image and set it as the caller's avatar."""

    user_public_id: UUID
    original_name: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class SetCategoryImageCommand:
    actor_public_id: UUID
    category_public_id: UUID
    original_name: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class SetPostIconCommand:
    """Upload an image and set it as a post's (thread's) icon."""

    actor_public_id: UUID
    post_public_id: UUID
    original_name: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class ListOwnerFilesQuery:
    owner_type: FileOwnerType
    owner_public_id: UUID


@dataclass(frozen=True, slots=True)
class ListMyFilesQuery:
    uploader_public_id: UUID
    limit: int = 20
    offset: int = 0


# --------------------------------------------------------------------------- #
# Projections (read models)                                                   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class VariantView:
    """One image rendition with a ready-to-use presigned URL."""

    name: str
    url: str
    width: int
    height: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class FileView:
    """Everything the frontend needs to display or download a file.

    ``url`` is disposition-aware (inline for media, attachment for documents);
    ``download_url`` always forces a download. ``variants`` holds thumbnail
    URLs for images.
    """

    public_id: UUID
    original_name: str
    content_type: str
    kind: FileKind
    size_bytes: int
    sha256: str | None
    status: str
    owner_type: str
    owner_id: UUID | None
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
    url: str
    download_url: str
    variants: dict[str, VariantView] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UploadTicket:
    """Presigned upload instructions handed back from ``request_upload``."""

    file_id: UUID
    storage_key: str
    upload_url: str
    method: str
    expires_in_seconds: int
    max_size_bytes: int
