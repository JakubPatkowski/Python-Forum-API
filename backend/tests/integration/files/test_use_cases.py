"""Use-case tests for the files module using in-memory fakes.

These exercise the application layer end-to-end (upload -> finalise -> attach
-> delete -> cleanup) without MinIO or a database, so they are fast and
deterministic. A separate test covers the real Pillow/libmagic processor.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.files.application.commands import (
    AttachFilesCommand,
    CompleteUploadCommand,
    DeleteFileCommand,
    DirectUploadCommand,
    RequestUploadCommand,
)
from app.modules.files.application.ports import ObjectStat, ProcessedVariant
from app.modules.files.application.use_cases import (
    AttachFilesUseCase,
    CleanupOrphansUseCase,
    CompleteUploadUseCase,
    DeleteFileUseCase,
    DirectUploadUseCase,
    RequestUploadUseCase,
)
from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import (
    FileKind,
    FileOwnerType,
    FileStatus,
    MimeType,
    Sha256,
    StorageKey,
)
from app.modules.identity.domain.user import UserId
from app.shared.application.result import Err, Ok

# --------------------------------------------------------------------------- #
# Fakes                                                                       #
# --------------------------------------------------------------------------- #


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.removed: list[str] = []

    async def ensure_bucket(self) -> None:
        return None

    async def presigned_put_url(self, key: str, *, content_type: str, expires_seconds: int) -> str:
        return f"https://minio.test/{key}?put=1"

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        disposition: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        return f"https://minio.test/{key}?disposition={disposition}"

    async def put_bytes(self, key: str, data: bytes, *, content_type: str) -> None:
        self.objects[key] = data

    async def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    async def stat(self, key: str) -> ObjectStat | None:
        if key in self.objects:
            return ObjectStat(size_bytes=len(self.objects[key]), content_type=None)
        return None

    async def remove(self, key: str) -> None:
        self.objects.pop(key, None)
        self.removed.append(key)

    async def remove_many(self, keys: Iterable[str]) -> None:
        for k in keys:
            self.objects.pop(k, None)
            self.removed.append(k)


class FakeProcessor:
    def __init__(self, *, sniff: str = "image/png") -> None:
        self._sniff = sniff

    def sniff_mime(self, data: bytes) -> str:
        return self._sniff

    def probe_image(self, data: bytes) -> tuple[int, int] | None:
        return (800, 600)

    def make_image_variants(self, data: bytes, *, sizes: dict[str, int]) -> list[ProcessedVariant]:
        return [
            ProcessedVariant(
                name="thumb",
                data=b"thumb-bytes",
                width=256,
                height=192,
                content_type="image/png",
            )
        ]


class FakeRepo:
    def __init__(self, store: dict[UUID, File]) -> None:
        self._store = store

    async def get(self, id_: FileId) -> File | None:
        return self._store.get(id_.value)

    async def add(self, entity: File) -> None:
        self._store[entity.id.value] = entity

    async def save(self, file: File) -> None:
        self._store[file.id.value] = file

    async def remove(self, entity: File) -> None:
        self._store.pop(entity.id.value, None)

    async def exists(self, id_: FileId) -> bool:
        return id_.value in self._store

    async def list_for_owner(self, owner_type: FileOwnerType, owner_public_id: UUID) -> list[File]:
        return [
            f
            for f in self._store.values()
            if f.owner_type is owner_type and f.owner_id == owner_public_id and f.is_ready
        ]

    async def list_by_uploader(
        self, uploader_public_id: UUID, *, limit: int, offset: int
    ) -> list[File]:
        items = [
            f
            for f in self._store.values()
            if f.uploader_id.value == uploader_public_id and f.is_ready
        ]
        return items[offset : offset + limit]

    async def list_orphans(self, *, older_than: datetime, limit: int) -> list[File]:
        items = [
            f
            for f in self._store.values()
            if f.owner_type is FileOwnerType.STANDALONE and f.created_at < older_than
        ]
        return items[:limit]


class FakeUoW:
    def __init__(self) -> None:
        self.store: dict[UUID, File] = {}
        self.files = FakeRepo(self.store)
        self.committed = 0
        self.post_authors: dict[UUID, UUID] = {}
        self.comment_authors: dict[UUID, UUID] = {}
        self.categories: set[UUID] = set()
        self.avatars: dict[UUID, UUID | None] = {}
        self._internal: dict[UUID, int] = {}
        self._counter = 0

    async def __aenter__(self) -> FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        return None

    async def resolve_user_id(self, user_public_id: UUID) -> int | None:
        return 1

    async def file_internal_id(self, file_public_id: UUID) -> int | None:
        if file_public_id not in self._internal:
            self._counter += 1
            self._internal[file_public_id] = self._counter
        return self._internal[file_public_id]

    async def get_post_author(self, post_public_id: UUID) -> UUID | None:
        return self.post_authors.get(post_public_id)

    async def get_comment_author(self, comment_public_id: UUID) -> UUID | None:
        return self.comment_authors.get(comment_public_id)

    async def category_exists(self, category_public_id: UUID) -> bool:
        return category_public_id in self.categories

    async def set_user_avatar(self, user_public_id: UUID, file_internal_id: int | None) -> None:
        public = next((p for p, i in self._internal.items() if i == file_internal_id), None)
        self.avatars[user_public_id] = public

    async def current_avatar_file_public_id(self, user_public_id: UUID) -> UUID | None:
        return self.avatars.get(user_public_id)

    async def current_category_image_file_public_id(self, category_public_id: UUID) -> UUID | None:
        matches = [
            f
            for f in self.store.values()
            if f.owner_type is FileOwnerType.CATEGORY and f.owner_id == category_public_id
        ]
        return matches[-1].id.value if matches else None


class FakeBus:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)

    def subscribe(self, *a: object, **k: object) -> None:
        return None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


def _ready_file(uploader: UUID, *, created_at: datetime | None = None) -> File:
    return File(
        id=FileId(uuid4()),
        uploader_id=UserId(uploader),
        storage_key=StorageKey("ab/cd/file.png"),
        original_name="file.png",
        content_type=MimeType("image/png"),
        status=FileStatus.READY,
        size_bytes=10,
        sha256=Sha256("c" * 64),
        created_at=created_at,
    )


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


class TestDirectUpload:
    async def test_image_upload_succeeds_with_thumbnail(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        uc = DirectUploadUseCase(uow, storage, FakeProcessor(), bus)

        result = await uc.execute(
            DirectUploadCommand(
                uploader_public_id=uuid4(),
                original_name="photo.png",
                content_type="image/png",
                data=b"\x89PNG\r\n\x1a\n fake image bytes",
            )
        )

        assert isinstance(result, Ok)
        view = result.value
        assert view.status == FileStatus.READY.value
        assert view.kind is FileKind.IMAGE
        assert view.sha256 is not None
        assert "thumb" in view.variants
        # Original + thumbnail were both stored.
        assert len(storage.objects) == 2
        assert any(isinstance(e, object) for e in bus.events)
        assert uow.committed == 1

    async def test_rejects_disallowed_sniffed_type(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        # Declared png (allowed) but the bytes sniff as html (blocked).
        uc = DirectUploadUseCase(uow, storage, FakeProcessor(sniff="text/html"), bus)

        result = await uc.execute(
            DirectUploadCommand(
                uploader_public_id=uuid4(),
                original_name="evil.png",
                content_type="image/png",
                data=b"<html>nope</html>",
            )
        )

        assert isinstance(result, Err)
        assert result.error.http_status == 415
        # The uploaded object was purged and nothing persisted.
        assert storage.objects == {}
        assert uow.store == {}


class TestAttach:
    async def test_author_can_attach_own_file_to_post(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        author = uuid4()
        post_id = uuid4()
        uow.post_authors[post_id] = author
        f = _ready_file(author)
        uow.store[f.id.value] = f

        uc = AttachFilesUseCase(uow, storage, bus)
        result = await uc.execute(
            AttachFilesCommand(
                actor_public_id=author,
                owner_type=FileOwnerType.POST,
                owner_public_id=post_id,
                file_ids=(f.id.value,),
            )
        )

        assert isinstance(result, Ok)
        assert uow.store[f.id.value].owner_type is FileOwnerType.POST
        assert uow.store[f.id.value].owner_id == post_id

    async def test_non_author_cannot_attach(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        author, intruder, post_id = uuid4(), uuid4(), uuid4()
        uow.post_authors[post_id] = author
        f = _ready_file(intruder)
        uow.store[f.id.value] = f

        uc = AttachFilesUseCase(uow, storage, bus)
        result = await uc.execute(
            AttachFilesCommand(
                actor_public_id=intruder,
                owner_type=FileOwnerType.POST,
                owner_public_id=post_id,
                file_ids=(f.id.value,),
            )
        )
        assert isinstance(result, Err)
        assert result.error.http_status == 403

    async def test_missing_post_is_not_found(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        actor = uuid4()
        f = _ready_file(actor)
        uow.store[f.id.value] = f
        uc = AttachFilesUseCase(uow, storage, bus)
        result = await uc.execute(
            AttachFilesCommand(
                actor_public_id=actor,
                owner_type=FileOwnerType.POST,
                owner_public_id=uuid4(),
                file_ids=(f.id.value,),
            )
        )
        assert isinstance(result, Err)
        assert result.error.http_status == 404


class TestDelete:
    async def test_uploader_can_delete(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        owner = uuid4()
        f = _ready_file(owner)
        uow.store[f.id.value] = f
        storage.objects["ab/cd/file.png"] = b"x"

        uc = DeleteFileUseCase(uow, storage, bus)
        result = await uc.execute(
            DeleteFileCommand(file_public_id=f.id.value, actor_public_id=owner)
        )
        assert isinstance(result, Ok)
        assert f.id.value not in uow.store
        assert "ab/cd/file.png" in storage.removed

    async def test_non_owner_denied(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        f = _ready_file(uuid4())
        uow.store[f.id.value] = f
        uc = DeleteFileUseCase(uow, storage, bus)
        result = await uc.execute(
            DeleteFileCommand(file_public_id=f.id.value, actor_public_id=uuid4())
        )
        assert isinstance(result, Err)
        assert result.error.http_status == 403


class TestCleanup:
    async def test_removes_old_standalone_files(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        old = _ready_file(uuid4(), created_at=datetime.now(UTC) - timedelta(hours=48))
        fresh = _ready_file(uuid4(), created_at=datetime.now(UTC))
        uow.store[old.id.value] = old
        uow.store[fresh.id.value] = fresh
        storage.objects["ab/cd/file.png"] = b"x"

        uc = CleanupOrphansUseCase(uow, storage, bus)
        result = await uc.execute(retention_hours=24, batch_size=100)

        assert isinstance(result, Ok)
        assert result.value == 1
        assert old.id.value not in uow.store
        assert fresh.id.value in uow.store


class TestPresignedFlow:
    async def test_request_then_complete(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        uploader = uuid4()

        req = RequestUploadUseCase(uow, storage)
        ticket_res = await req.execute(
            RequestUploadCommand(
                uploader_public_id=uploader,
                original_name="p.png",
                content_type="image/png",
                size_bytes=10,
            )
        )
        assert isinstance(ticket_res, Ok)
        ticket = ticket_res.value
        # File row exists, still pending.
        assert uow.store[ticket.file_id].status is FileStatus.PENDING

        # Simulate the browser PUTting bytes to MinIO.
        storage.objects[ticket.storage_key] = b"\x89PNG fake"

        comp = CompleteUploadUseCase(uow, storage, FakeProcessor(), bus)
        done = await comp.execute(
            CompleteUploadCommand(file_public_id=ticket.file_id, actor_public_id=uploader)
        )
        assert isinstance(done, Ok)
        assert done.value.status == FileStatus.READY.value
        assert "thumb" in done.value.variants

    async def test_complete_without_upload_is_conflict(self) -> None:
        uow, storage, bus = FakeUoW(), FakeStorage(), FakeBus()
        uploader = uuid4()
        req = RequestUploadUseCase(uow, storage)
        ticket = (
            await req.execute(
                RequestUploadCommand(
                    uploader_public_id=uploader,
                    original_name="p.png",
                    content_type="image/png",
                    size_bytes=10,
                )
            )
        ).value  # type: ignore[union-attr]

        comp = CompleteUploadUseCase(uow, storage, FakeProcessor(), bus)
        result = await comp.execute(
            CompleteUploadCommand(file_public_id=ticket.file_id, actor_public_id=uploader)
        )
        assert isinstance(result, Err)
        assert result.error.http_status == 409


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg"])
def test_smoke_mime_kinds(mime: str) -> None:
    assert MimeType(mime).is_image
