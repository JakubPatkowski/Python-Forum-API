"""Use-case tests dla obrazów właścicielskich (avatar / obraz kategorii / ikona
wątku) oraz odczytów (get/list) — wszystko na fake'ach in-memory, bez MinIO i bez
bazy. Domykają gałęzie use-case'ów files, których nie dotyka szczęśliwa ścieżka
HTTP: podmiana starego pliku, walidacja typu, brak właściciela, widoczność.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.files.application.commands import (
    ListMyFilesQuery,
    ListOwnerFilesQuery,
    SetAvatarCommand,
    SetCategoryImageCommand,
    SetPostIconCommand,
)
from app.modules.files.application.ports import ObjectStat, ProcessedVariant
from app.modules.files.application.use_cases import (
    GetAvatarUseCase,
    GetCategoryImageUseCase,
    GetFileUseCase,
    GetPostIconUseCase,
    ListMyFilesUseCase,
    ListOwnerFilesUseCase,
    SetAvatarUseCase,
    SetCategoryImageUseCase,
    SetPostIconUseCase,
)
from app.modules.files.domain.events import (
    AvatarChanged,
    CategoryImageChanged,
    PostIconChanged,
)
from app.modules.files.domain.file import File, FileId
from app.modules.files.domain.value_objects import (
    FileOwnerType,
    FileStatus,
    MimeType,
    Sha256,
    StorageKey,
)
from app.modules.identity.domain.user import UserId
from app.shared.application.result import Err, Ok

PNG = b"\x89PNG\r\n\x1a\n fake image bytes"


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
    def sniff_mime(self, data: bytes) -> str:
        return "image/png"

    def probe_image(self, data: bytes) -> tuple[int, int] | None:
        return (800, 600)

    def make_image_variants(self, data: bytes, *, sizes: dict[str, int]) -> list[ProcessedVariant]:
        return [
            ProcessedVariant(
                name="thumb", data=b"thumb-bytes", width=256, height=192, content_type="image/png"
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


class FakeUoW:
    def __init__(self) -> None:
        self.store: dict[UUID, File] = {}
        self.files = FakeRepo(self.store)
        self.committed = 0
        self.categories: set[UUID] = set()
        self.post_authors: dict[UUID, UUID] = {}
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

    async def file_internal_id(self, file_public_id: UUID) -> int | None:
        if file_public_id not in self._internal:
            self._counter += 1
            self._internal[file_public_id] = self._counter
        return self._internal[file_public_id]

    async def category_exists(self, category_public_id: UUID) -> bool:
        return category_public_id in self.categories

    async def get_post_author(self, post_public_id: UUID) -> UUID | None:
        return self.post_authors.get(post_public_id)

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

    async def current_post_icon_file_public_id(self, post_public_id: UUID) -> UUID | None:
        matches = [
            f
            for f in self.store.values()
            if f.owner_type is FileOwnerType.POST_ICON and f.owner_id == post_public_id
        ]
        return matches[-1].id.value if matches else None


def _deps() -> tuple[FakeUoW, FakeStorage, FakeProcessor, FakeBus]:
    return FakeUoW(), FakeStorage(), FakeProcessor(), FakeBus()


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


def _attached_file(uploader: UUID, *, owner_type: FileOwnerType, owner: UUID) -> File:
    f = File(
        id=FileId(uuid4()),
        uploader_id=UserId(uploader),
        storage_key=StorageKey("ab/cd/old.png"),
        original_name="old.png",
        content_type=MimeType("image/png"),
        status=FileStatus.READY,
        size_bytes=10,
        sha256=Sha256("c" * 64),
        created_at=datetime.now(UTC),
    )
    f.attach_to(owner_type=owner_type, owner_public_id=owner)
    f.pull_events()
    return f


# --------------------------------------------------------------------------- #
# SetAvatar                                                                   #
# --------------------------------------------------------------------------- #


class TestSetAvatar:
    async def test_sets_avatar_and_emits_event(self) -> None:
        uow, storage, proc, bus = _deps()
        user = uuid4()
        uc = SetAvatarUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetAvatarCommand(
                user_public_id=user, original_name="me.png", content_type="image/png", data=PNG
            )
        )
        assert isinstance(res, Ok)
        assert res.value.owner_type == FileOwnerType.USER_AVATAR.value
        assert uow.committed == 1
        assert any(isinstance(e, AvatarChanged) for e in bus.events)
        assert await uow.current_avatar_file_public_id(user) == res.value.public_id

    async def test_replaces_previous_avatar(self) -> None:
        uow, storage, proc, bus = _deps()
        user = uuid4()
        old = _attached_file(user, owner_type=FileOwnerType.USER_AVATAR, owner=user)
        uow.store[old.id.value] = old
        await uow.file_internal_id(old.id.value)
        uow.avatars[user] = old.id.value
        storage.objects["ab/cd/old.png"] = b"x"

        uc = SetAvatarUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetAvatarCommand(
                user_public_id=user, original_name="new.png", content_type="image/png", data=PNG
            )
        )
        assert isinstance(res, Ok)
        assert old.id.value not in uow.store
        assert "ab/cd/old.png" in storage.removed

    async def test_rejects_non_image(self) -> None:
        uow, storage, proc, bus = _deps()
        uc = SetAvatarUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetAvatarCommand(
                user_public_id=uuid4(),
                original_name="x.pdf",
                content_type="application/pdf",
                data=b"%PDF-",
            )
        )
        assert isinstance(res, Err)
        assert res.error.http_status == 415
        assert uow.store == {}


# --------------------------------------------------------------------------- #
# SetCategoryImage                                                            #
# --------------------------------------------------------------------------- #


class TestSetCategoryImage:
    async def test_missing_category_is_not_found(self) -> None:
        uow, storage, proc, bus = _deps()
        uc = SetCategoryImageUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetCategoryImageCommand(
                actor_public_id=uuid4(),
                category_public_id=uuid4(),
                original_name="c.png",
                content_type="image/png",
                data=PNG,
            )
        )
        assert isinstance(res, Err)
        assert res.error.http_status == 404

    async def test_sets_image_and_replaces_old(self) -> None:
        uow, storage, proc, bus = _deps()
        actor, category = uuid4(), uuid4()
        uow.categories.add(category)
        old = _attached_file(actor, owner_type=FileOwnerType.CATEGORY, owner=category)
        uow.store[old.id.value] = old
        storage.objects["ab/cd/old.png"] = b"x"

        uc = SetCategoryImageUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetCategoryImageCommand(
                actor_public_id=actor,
                category_public_id=category,
                original_name="c.png",
                content_type="image/png",
                data=PNG,
            )
        )
        assert isinstance(res, Ok)
        assert any(isinstance(e, CategoryImageChanged) for e in bus.events)
        assert old.id.value not in uow.store
        assert "ab/cd/old.png" in storage.removed

    async def test_rejects_non_image(self) -> None:
        uow, storage, proc, bus = _deps()
        category = uuid4()
        uow.categories.add(category)
        uc = SetCategoryImageUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetCategoryImageCommand(
                actor_public_id=uuid4(),
                category_public_id=category,
                original_name="x.txt",
                content_type="text/plain",
                data=b"hi",
            )
        )
        assert isinstance(res, Err)
        assert res.error.http_status == 415


# --------------------------------------------------------------------------- #
# SetPostIcon                                                                 #
# --------------------------------------------------------------------------- #


class TestSetPostIcon:
    async def test_missing_post_is_not_found(self) -> None:
        uow, storage, proc, bus = _deps()
        uc = SetPostIconUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetPostIconCommand(
                actor_public_id=uuid4(),
                post_public_id=uuid4(),
                original_name="i.png",
                content_type="image/png",
                data=PNG,
            )
        )
        assert isinstance(res, Err)
        assert res.error.http_status == 404

    async def test_sets_icon_and_emits_event(self) -> None:
        uow, storage, proc, bus = _deps()
        author, post = uuid4(), uuid4()
        uow.post_authors[post] = author
        uc = SetPostIconUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetPostIconCommand(
                actor_public_id=author,
                post_public_id=post,
                original_name="i.png",
                content_type="image/png",
                data=PNG,
            )
        )
        assert isinstance(res, Ok)
        assert res.value.owner_type == FileOwnerType.POST_ICON.value
        assert any(isinstance(e, PostIconChanged) for e in bus.events)

    async def test_replaces_old_icon(self) -> None:
        uow, storage, proc, bus = _deps()
        author, post = uuid4(), uuid4()
        uow.post_authors[post] = author
        old = _attached_file(author, owner_type=FileOwnerType.POST_ICON, owner=post)
        uow.store[old.id.value] = old
        storage.objects["ab/cd/old.png"] = b"x"

        uc = SetPostIconUseCase(uow, storage, proc, bus)
        res = await uc.execute(
            SetPostIconCommand(
                actor_public_id=author,
                post_public_id=post,
                original_name="i.png",
                content_type="image/png",
                data=PNG,
            )
        )
        assert isinstance(res, Ok)
        assert old.id.value not in uow.store
        assert "ab/cd/old.png" in storage.removed


# --------------------------------------------------------------------------- #
# Get owner image (avatar / category / post icon)                            #
# --------------------------------------------------------------------------- #


class TestGetOwnerImage:
    async def test_get_avatar_none_when_unset(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        res = await GetAvatarUseCase(uow, storage).execute(uuid4())
        assert isinstance(res, Ok)
        assert res.value is None

    async def test_get_avatar_returns_view(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        user = uuid4()
        f = _attached_file(user, owner_type=FileOwnerType.USER_AVATAR, owner=user)
        uow.store[f.id.value] = f
        uow.avatars[user] = f.id.value
        res = await GetAvatarUseCase(uow, storage).execute(user)
        assert isinstance(res, Ok)
        assert res.value is not None
        assert res.value.public_id == f.id.value

    async def test_get_category_image(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        category = uuid4()
        f = _attached_file(uuid4(), owner_type=FileOwnerType.CATEGORY, owner=category)
        uow.store[f.id.value] = f
        res = await GetCategoryImageUseCase(uow, storage).execute(category)
        assert isinstance(res, Ok)
        assert res.value is not None
        assert res.value.public_id == f.id.value

    async def test_get_post_icon_none_when_unset(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        res = await GetPostIconUseCase(uow, storage).execute(uuid4())
        assert isinstance(res, Ok)
        assert res.value is None

    async def test_get_post_icon_returns_view(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        post = uuid4()
        f = _attached_file(uuid4(), owner_type=FileOwnerType.POST_ICON, owner=post)
        uow.store[f.id.value] = f
        res = await GetPostIconUseCase(uow, storage).execute(post)
        assert isinstance(res, Ok)
        assert res.value is not None


# --------------------------------------------------------------------------- #
# GetFile (visibility rules)                                                  #
# --------------------------------------------------------------------------- #


class TestGetFile:
    async def test_missing_is_not_found(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        res = await GetFileUseCase(uow, storage).execute(uuid4())
        assert isinstance(res, Err)
        assert res.error.http_status == 404

    async def test_attached_file_is_public(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        f = _attached_file(uuid4(), owner_type=FileOwnerType.POST, owner=uuid4())
        uow.store[f.id.value] = f
        res = await GetFileUseCase(uow, storage).execute(f.id.value)
        assert isinstance(res, Ok)
        assert res.value.public_id == f.id.value

    async def test_standalone_private_to_uploader(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        uploader = uuid4()
        f = File(
            id=FileId(uuid4()),
            uploader_id=UserId(uploader),
            storage_key=StorageKey("ab/cd/s.png"),
            original_name="s.png",
            content_type=MimeType("image/png"),
            status=FileStatus.READY,
            size_bytes=10,
            sha256=Sha256("c" * 64),
            created_at=datetime.now(UTC),
        )
        uow.store[f.id.value] = f
        # stranger -> 404
        other = await GetFileUseCase(uow, storage).execute(f.id.value, actor_public_id=uuid4())
        assert isinstance(other, Err)
        # uploader -> Ok
        mine = await GetFileUseCase(uow, storage).execute(f.id.value, actor_public_id=uploader)
        assert isinstance(mine, Ok)


# --------------------------------------------------------------------------- #
# List use-cases                                                              #
# --------------------------------------------------------------------------- #


class TestListUseCases:
    async def test_list_my_files(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        uploader = uuid4()
        for _ in range(3):
            f = _attached_file(uploader, owner_type=FileOwnerType.POST, owner=uuid4())
            uow.store[f.id.value] = f
        res = await ListMyFilesUseCase(uow, storage).execute(
            ListMyFilesQuery(uploader_public_id=uploader, limit=10, offset=0)
        )
        assert isinstance(res, Ok)
        assert len(res.value) == 3

    async def test_list_owner_files(self) -> None:
        uow, storage = FakeUoW(), FakeStorage()
        post = uuid4()
        f1 = _attached_file(uuid4(), owner_type=FileOwnerType.POST, owner=post)
        f2 = _attached_file(uuid4(), owner_type=FileOwnerType.POST, owner=uuid4())
        uow.store[f1.id.value] = f1
        uow.store[f2.id.value] = f2
        res = await ListOwnerFilesUseCase(uow, storage).execute(
            ListOwnerFilesQuery(owner_type=FileOwnerType.POST, owner_public_id=post)
        )
        assert isinstance(res, Ok)
        assert {v.public_id for v in res.value} == {f1.id.value}
