"""Unit tests for the File aggregate lifecycle and invariants."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.files.domain.events import (
    FileAttached,
    FileDeleted,
    FileDetached,
    FileUploaded,
)
from app.modules.files.domain.file import File
from app.modules.files.domain.value_objects import (
    FileOwnerType,
    FileStatus,
    ImageVariant,
    MimeType,
    Sha256,
    StorageKey,
)
from app.modules.identity.domain.user import UserId
from app.shared.domain.errors import ConflictError, ValidationError


def _pending(content_type: str = "image/png") -> File:
    return File.request_upload(
        uploader_id=UserId(uuid4()),
        storage_key=StorageKey("ab/cd/abc123.png"),
        original_name="photo.png",
        content_type=MimeType(content_type),
    )


def _ready_kwargs() -> dict:
    return {
        "size_bytes": 2048,
        "sha256": Sha256("b" * 64),
        "width": 800,
        "height": 600,
        "variants": {
            "thumb": ImageVariant(
                name="thumb",
                storage_key=StorageKey("ab/cd/abc123__thumb.png"),
                width=256,
                height=192,
                size_bytes=512,
            )
        },
    }


class TestRequestUpload:
    def test_starts_pending_and_standalone(self) -> None:
        f = _pending()
        assert f.status is FileStatus.PENDING
        assert f.owner_type is FileOwnerType.STANDALONE
        assert f.is_ready is False
        assert f.is_attached is False
        assert f.pull_events() == []

    def test_requires_original_name(self) -> None:
        with pytest.raises(ValidationError):
            File.request_upload(
                uploader_id=UserId(uuid4()),
                storage_key=StorageKey("ab/cd/x.png"),
                original_name="   ",
                content_type=MimeType("image/png"),
            )


class TestMarkReady:
    def test_transitions_to_ready_and_emits_event(self) -> None:
        f = _pending()
        f.mark_ready(**_ready_kwargs())
        assert f.is_ready is True
        assert f.width == 800
        assert "thumb" in f.variants
        events = f.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], FileUploaded)

    def test_double_finalise_raises(self) -> None:
        f = _pending()
        f.mark_ready(**_ready_kwargs())
        with pytest.raises(ConflictError):
            f.mark_ready(**_ready_kwargs())


class TestAttachDetach:
    def test_attach_requires_ready(self) -> None:
        f = _pending()
        with pytest.raises(ConflictError):
            f.attach_to(owner_type=FileOwnerType.POST, owner_public_id=uuid4())

    def test_attach_then_detach(self) -> None:
        f = _pending()
        f.mark_ready(**_ready_kwargs())
        f.pull_events()  # drop FileUploaded
        owner = uuid4()
        f.attach_to(owner_type=FileOwnerType.POST, owner_public_id=owner)
        assert f.is_attached is True
        assert f.owner_type is FileOwnerType.POST
        assert f.owner_id == owner
        attach_events = f.pull_events()
        assert isinstance(attach_events[0], FileAttached)

        f.detach()
        assert f.is_attached is False
        assert f.owner_type is FileOwnerType.STANDALONE
        assert isinstance(f.pull_events()[0], FileDetached)

    def test_cannot_attach_to_standalone(self) -> None:
        f = _pending()
        f.mark_ready(**_ready_kwargs())
        with pytest.raises(ValidationError):
            f.attach_to(owner_type=FileOwnerType.STANDALONE, owner_public_id=uuid4())


class TestDeletionAndKeys:
    def test_all_storage_keys_includes_variants(self) -> None:
        f = _pending()
        f.mark_ready(**_ready_kwargs())
        keys = f.all_storage_keys()
        assert "ab/cd/abc123.png" in keys
        assert "ab/cd/abc123__thumb.png" in keys

    def test_record_deletion_emits_event_with_keys(self) -> None:
        f = _pending()
        f.mark_ready(**_ready_kwargs())
        f.pull_events()
        f.record_deletion()
        event = f.pull_events()[0]
        assert isinstance(event, FileDeleted)
        assert event.storage_key == "ab/cd/abc123.png"
        assert "ab/cd/abc123__thumb.png" in event.variant_keys

    def test_default_disposition(self) -> None:
        img = _pending("image/png")
        doc = _pending("application/pdf")
        assert img.default_disposition() == "inline"
        assert doc.default_disposition() == "attachment"
