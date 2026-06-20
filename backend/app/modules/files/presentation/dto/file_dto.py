"""Pydantic request/response DTOs for the files endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.files.application.commands import FileView, UploadTicket, VariantView

# --------------------------------------------------------------------------- #
# Requests                                                                    #
# --------------------------------------------------------------------------- #


class RequestUploadRequest(BaseModel):
    """Body for ``POST /files/uploads`` (start a presigned upload)."""

    model_config = ConfigDict(extra="forbid")

    original_name: Annotated[str, Field(min_length=1, max_length=255)]
    content_type: Annotated[str, Field(min_length=3, max_length=150)]
    size_bytes: Annotated[int, Field(gt=0)]


class AttachFilesRequest(BaseModel):
    """Body for attaching already-uploaded files to an owner."""

    model_config = ConfigDict(extra="forbid")

    file_ids: Annotated[list[UUID], Field(min_length=1, max_length=20)]


# --------------------------------------------------------------------------- #
# Responses                                                                   #
# --------------------------------------------------------------------------- #


class VariantResponse(BaseModel):
    name: str
    url: str
    width: int
    height: int
    size_bytes: int

    @classmethod
    def from_view(cls, v: VariantView) -> VariantResponse:
        return cls(
            name=v.name,
            url=v.url,
            width=v.width,
            height=v.height,
            size_bytes=v.size_bytes,
        )


class FileResponse(BaseModel):
    """Everything the client needs to render or download a file."""

    id: UUID
    original_name: str
    content_type: str
    kind: str
    size_bytes: int
    sha256: str | None
    status: str
    owner_type: str
    owner_id: UUID | None
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
    # Disposition-aware URL (inline for media, attachment for documents).
    url: str
    # Always forces a download.
    download_url: str
    variants: dict[str, VariantResponse] = Field(default_factory=dict)

    @classmethod
    def from_view(cls, v: FileView) -> FileResponse:
        return cls(
            id=v.public_id,
            original_name=v.original_name,
            content_type=v.content_type,
            kind=v.kind.value,
            size_bytes=v.size_bytes,
            sha256=v.sha256,
            status=v.status,
            owner_type=v.owner_type,
            owner_id=v.owner_id,
            width=v.width,
            height=v.height,
            created_at=v.created_at,
            updated_at=v.updated_at,
            url=v.url,
            download_url=v.download_url,
            variants={name: VariantResponse.from_view(var) for name, var in v.variants.items()},
        )


class UploadTicketResponse(BaseModel):
    """Presigned upload instructions returned by ``POST /files/uploads``."""

    file_id: UUID
    storage_key: str
    upload_url: str
    method: str
    expires_in_seconds: int
    max_size_bytes: int

    @classmethod
    def from_ticket(cls, t: UploadTicket) -> UploadTicketResponse:
        return cls(
            file_id=t.file_id,
            storage_key=t.storage_key,
            upload_url=t.upload_url,
            method=t.method,
            expires_in_seconds=t.expires_in_seconds,
            max_size_bytes=t.max_size_bytes,
        )
