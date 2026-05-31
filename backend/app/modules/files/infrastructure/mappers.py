"""Mappers between ``FileOrm`` rows and the :class:`File` aggregate.

Note on ids: the domain ``File`` carries the *uploader's* public UUID, while
the row stores the legacy integer FK. The repository therefore joins ``users``
and passes ``uploader_public_id`` here. ``owner_id`` (also a public UUID) is
only reconstructed where the caller already knows it (``list_for_owner``);
elsewhere it is left ``None`` since ``is_attached`` derives from ``owner_type``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import (
    FileOwnerType,
    FileStatus,
    ImageVariant,
    MimeType,
    Sha256,
    StorageKey,
)
from app.modules.files.infrastructure.orm import FileOrm
from app.modules.identity.domain.user import UserId


def variants_to_json(variants: dict[str, ImageVariant]) -> dict[str, Any]:
    """Serialise image variants to a JSON-storable dict."""
    return {
        name: {
            "storage_key": str(v.storage_key),
            "width": v.width,
            "height": v.height,
            "size_bytes": v.size_bytes,
        }
        for name, v in variants.items()
    }


def variants_from_json(raw: dict[str, Any] | None) -> dict[str, ImageVariant]:
    if not raw:
        return {}
    out: dict[str, ImageVariant] = {}
    for name, v in raw.items():
        out[name] = ImageVariant(
            name=name,
            storage_key=StorageKey(v["storage_key"]),
            width=int(v["width"]),
            height=int(v["height"]),
            size_bytes=int(v["size_bytes"]),
        )
    return out


def _enum_value(raw: Any) -> str:
    """SAEnum may return the Python enum or its raw string — normalise to str."""
    return raw.value if hasattr(raw, "value") else str(raw)


def file_from_orm(
    row: FileOrm,
    *,
    uploader_public_id: UUID,
    owner_public_id: UUID | None = None,
) -> File:
    """Build a domain :class:`File` from an ORM row + the joined uploader id."""
    return File(
        id=FileId(row.public_id),
        uploader_id=UserId(uploader_public_id),
        storage_key=StorageKey(row.storage_key),
        original_name=row.original_name,
        content_type=MimeType(row.content_type),
        status=FileStatus(_enum_value(row.status)),
        size_bytes=int(row.size_bytes or 0),
        sha256=Sha256(row.sha256) if row.sha256 else None,
        owner_type=FileOwnerType(_enum_value(row.owner_type)),
        owner_id=owner_public_id,
        width=row.width,
        height=row.height,
        variants=variants_from_json(row.variants),
        created_at=_as_aware(row.created_at),
        updated_at=_as_aware(row.updated_at) if row.updated_at else None,
    )


def _as_aware(dt: datetime) -> datetime:
    """Treat naive timestamps coming from psycopg as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
