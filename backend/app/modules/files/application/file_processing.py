"""Shared helpers used by several file use cases.

Centralises the parts that would otherwise be duplicated between the
presigned (``complete``) and proxied (``direct``) upload paths:

* picking a safe object key,
* validating the declared vs. sniffed MIME type,
* finalising a :class:`File` (sha-256, image probe, thumbnails),
* building a :class:`FileView` with freshly-minted presigned URLs.
"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from uuid import uuid4

from app.config import settings
from app.modules.files.application.commands import FileView, VariantView
from app.modules.files.application.errors import FileTooLarge, UnsupportedFileType
from app.modules.files.application.ports import IFileProcessor, IFileStorage
from app.modules.files.domain.file import File
from app.modules.files.domain.value_objects import (
    ImageVariant,
    MimeType,
    Sha256,
    StorageKey,
)

_EXT_MAX = 12


def generate_storage_key(original_name: str) -> StorageKey:
    """Build a collision-free object key: ``ab/cd/<uuid>.<ext>``.

    The two-level prefix keeps any single bucket 'directory' from growing
    unbounded. The extension is taken from the original name (sanitised).
    """
    ext = PurePosixPath(original_name).suffix.lower()
    if len(ext) > _EXT_MAX or not ext[1:].isalnum():
        ext = ""
    token = uuid4().hex
    return StorageKey(f"{token[:2]}/{token[2:4]}/{token}{ext}")


def _variant_key(original: StorageKey, name: str) -> StorageKey:
    p = PurePosixPath(str(original))
    return StorageKey(str(p.with_name(f"{p.stem}__{name}{p.suffix}")))


def validate_declared_type(content_type: str) -> MimeType:
    """Validate the client-declared MIME against the whitelist (fast reject)."""
    mime = MimeType(content_type)  # syntactic validation
    if mime.value not in settings.ALLOWED_MIME_TYPES:
        raise UnsupportedFileType(mime.value)
    return mime


def resolve_content_type(declared: MimeType, sniffed: str) -> MimeType:
    """Reconcile declared vs. sniffed type; raise 415 if the bytes are unsafe.

    Returns the MIME type to actually store (prefers the sniffed one when it is
    explicitly whitelisted, otherwise falls back to the declared type for
    generic containers such as OOXML/zip).
    """
    if sniffed in settings.SNIFF_BLOCKED_MIME_TYPES:
        raise UnsupportedFileType(sniffed)
    if sniffed in settings.ALLOWED_MIME_TYPES:
        return MimeType(sniffed)
    same_family = sniffed.split("/", 1)[0] == declared.value.split("/", 1)[0]
    if (sniffed in settings.SNIFF_GENERIC_MIME_TYPES or same_family) and (
        declared.value in settings.ALLOWED_MIME_TYPES
    ):
        return declared
    raise UnsupportedFileType(sniffed)


def enforce_size(size: int) -> None:
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise FileTooLarge(size=size, limit=settings.MAX_UPLOAD_SIZE_BYTES)


async def finalize_file(
    file: File,
    data: bytes,
    *,
    declared: MimeType,
    processor: IFileProcessor,
    storage: IFileStorage,
) -> None:
    """Validate bytes and move ``file`` from PENDING to READY.

    Sniffs the MIME type, computes sha-256, and for images probes dimensions
    and uploads thumbnails before recording the aggregate as ready.
    """
    enforce_size(len(data))
    sniffed = processor.sniff_mime(data)
    content_type = resolve_content_type(declared, sniffed)
    sha = Sha256(hashlib.sha256(data).hexdigest())

    width: int | None = None
    height: int | None = None
    variants: dict[str, ImageVariant] = {}

    if content_type.is_image:
        dims = processor.probe_image(data)
        if dims is not None:
            width, height = dims
        for variant in processor.make_image_variants(data, sizes=settings.IMAGE_THUMBNAIL_SIZES):
            key = _variant_key(file.storage_key, variant.name)
            await storage.put_bytes(str(key), variant.data, content_type=variant.content_type)
            variants[variant.name] = ImageVariant(
                name=variant.name,
                storage_key=key,
                width=variant.width,
                height=variant.height,
                size_bytes=len(variant.data),
            )

    file.mark_ready(
        size_bytes=len(data),
        sha256=sha,
        content_type=content_type,
        width=width,
        height=height,
        variants=variants,
    )


async def build_file_view(file: File, *, storage: IFileStorage) -> FileView:
    """Project a :class:`File` into a :class:`FileView` with presigned URLs."""
    ttl = settings.FILE_DOWNLOAD_URL_TTL_SECONDS
    url = await storage.presigned_get_url(
        str(file.storage_key),
        expires_seconds=ttl,
        disposition=file.default_disposition(),
        filename=file.original_name,
        content_type=str(file.content_type),
    )
    download_url = await storage.presigned_get_url(
        str(file.storage_key),
        expires_seconds=ttl,
        disposition="attachment",
        filename=file.original_name,
        content_type=str(file.content_type),
    )
    variants: dict[str, VariantView] = {}
    for name, variant in file.variants.items():
        v_url = await storage.presigned_get_url(
            str(variant.storage_key),
            expires_seconds=ttl,
            disposition="inline",
            content_type=str(file.content_type),
        )
        variants[name] = VariantView(
            name=name,
            url=v_url,
            width=variant.width,
            height=variant.height,
            size_bytes=variant.size_bytes,
        )

    return FileView(
        public_id=file.id.value,
        original_name=file.original_name,
        content_type=str(file.content_type),
        kind=file.kind,
        size_bytes=file.size_bytes,
        sha256=str(file.sha256) if file.sha256 else None,
        status=file.status.value,
        owner_type=file.owner_type.value,
        owner_id=file.owner_id,
        width=file.width,
        height=file.height,
        created_at=file.created_at,
        updated_at=file.updated_at,
        url=url,
        download_url=download_url,
        variants=variants,
    )
