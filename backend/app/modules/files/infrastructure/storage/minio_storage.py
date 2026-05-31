"""MinIO (S3-compatible) implementation of :class:`IFileStorage`.

Two clients, one bucket:

* ``_internal`` talks to ``MINIO_ENDPOINT`` (in-cluster) for all server-side
  byte operations — put / get / stat / remove.
* ``_public`` is configured with ``MINIO_PUBLIC_ENDPOINT`` and is used *only*
  to mint presigned URLs, so the host baked into the signature is the one the
  **browser** can reach. An explicit ``region`` is passed so presigning never
  triggers a bucket-location lookup against the (possibly unreachable) public
  endpoint.

All blocking minio-py calls run in a worker thread via ``anyio.to_thread`` so
they do not block the event loop.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from io import BytesIO

import anyio
import structlog
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from app.config import settings
from app.modules.files.application.ports import IFileStorage, ObjectStat

logger = structlog.get_logger(__name__)


class MinioFileStorage(IFileStorage):
    """Object storage backed by MinIO."""

    def __init__(self) -> None:
        self._bucket = settings.MINIO_BUCKET
        self._internal = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION,
        )
        self._public = Minio(
            settings.minio_public_endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION,
        )

    async def ensure_bucket(self) -> None:
        await anyio.to_thread.run_sync(self._ensure_bucket_sync)

    def _ensure_bucket_sync(self) -> None:
        if not self._internal.bucket_exists(self._bucket):
            self._internal.make_bucket(self._bucket)
            logger.info("minio_bucket_created", bucket=self._bucket)

    async def presigned_put_url(
        self, key: str, *, content_type: str, expires_seconds: int
    ) -> str:
        # content_type is informational: a PUT presign does not sign headers.
        return await anyio.to_thread.run_sync(
            lambda: self._public.presigned_put_object(
                self._bucket, key, expires=timedelta(seconds=expires_seconds)
            )
        )

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        disposition: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        response_headers: dict[str, str] = {}
        if disposition is not None:
            value = disposition
            if filename:
                # RFC 5987 / 6266 — handle non-ASCII names safely.
                from urllib.parse import quote

                value = f"{disposition}; filename*=UTF-8''{quote(filename)}"
            response_headers["response-content-disposition"] = value
        if content_type is not None:
            response_headers["response-content-type"] = content_type

        return await anyio.to_thread.run_sync(
            lambda: self._public.presigned_get_object(
                self._bucket,
                key,
                expires=timedelta(seconds=expires_seconds),
                response_headers=response_headers or None,
            )
        )

    async def put_bytes(self, key: str, data: bytes, *, content_type: str) -> None:
        await anyio.to_thread.run_sync(
            lambda: self._internal.put_object(
                self._bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        )

    async def get_bytes(self, key: str) -> bytes:
        return await anyio.to_thread.run_sync(self._get_bytes_sync, key)

    def _get_bytes_sync(self, key: str) -> bytes:
        response = None
        try:
            response = self._internal.get_object(self._bucket, key)
            return response.read()
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    async def stat(self, key: str) -> ObjectStat | None:
        return await anyio.to_thread.run_sync(self._stat_sync, key)

    def _stat_sync(self, key: str) -> ObjectStat | None:
        try:
            obj = self._internal.stat_object(self._bucket, key)
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject", "NotFound"):
                return None
            raise
        return ObjectStat(size_bytes=obj.size or 0, content_type=obj.content_type)

    async def remove(self, key: str) -> None:
        await anyio.to_thread.run_sync(
            lambda: self._internal.remove_object(self._bucket, key)
        )

    async def remove_many(self, keys: Iterable[str]) -> None:
        key_list = [k for k in keys if k]
        if not key_list:
            return
        await anyio.to_thread.run_sync(self._remove_many_sync, key_list)

    def _remove_many_sync(self, keys: list[str]) -> None:
        errors = self._internal.remove_objects(
            self._bucket, (DeleteObject(k) for k in keys)
        )
        for error in errors:
            logger.warning("minio_delete_failed", error=str(error))
