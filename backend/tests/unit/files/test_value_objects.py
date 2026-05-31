"""Unit tests for files value objects — pure validation, no I/O."""

from __future__ import annotations

import pytest

from app.modules.files.domain.value_objects import (
    ByteSize,
    FileKind,
    ImageVariant,
    MimeType,
    Sha256,
    StorageKey,
)
from app.shared.domain.errors import ValidationError


class TestMimeType:
    @pytest.mark.parametrize(
        ("value", "kind"),
        [
            ("image/png", FileKind.IMAGE),
            ("image/jpeg", FileKind.IMAGE),
            ("video/mp4", FileKind.VIDEO),
            ("audio/mpeg", FileKind.AUDIO),
            ("application/pdf", FileKind.DOCUMENT),
            ("text/markdown", FileKind.DOCUMENT),
        ],
    )
    def test_kind_derivation(self, value: str, kind: FileKind) -> None:
        assert MimeType(value).kind is kind

    def test_renders_inline_for_media_only(self) -> None:
        assert MimeType("image/png").renders_inline is True
        assert MimeType("video/mp4").renders_inline is True
        assert MimeType("audio/mpeg").renders_inline is True
        assert MimeType("application/pdf").renders_inline is False

    def test_is_image(self) -> None:
        assert MimeType("image/webp").is_image is True
        assert MimeType("application/pdf").is_image is False

    @pytest.mark.parametrize("bad", ["", "image", "image/", "/png", "no slash here"])
    def test_rejects_malformed(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            MimeType(bad)


class TestByteSize:
    def test_accepts_positive(self) -> None:
        assert int(ByteSize(123)) == 123

    @pytest.mark.parametrize("bad", [0, -1, -999])
    def test_rejects_non_positive(self, bad: int) -> None:
        with pytest.raises(ValidationError):
            ByteSize(bad)


class TestSha256:
    def test_accepts_valid_digest(self) -> None:
        digest = "a" * 64
        assert str(Sha256(digest)) == digest

    @pytest.mark.parametrize("bad", ["abc", "A" * 64, "g" * 64, "a" * 63])
    def test_rejects_invalid(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            Sha256(bad)


class TestStorageKey:
    def test_accepts_typical_key(self) -> None:
        assert str(StorageKey("ab/cd/deadbeef.png")) == "ab/cd/deadbeef.png"

    @pytest.mark.parametrize("bad", ["", "/leading", "has space.png", "../escape"])
    def test_rejects_unsafe(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            StorageKey(bad)


class TestImageVariant:
    def test_valid(self) -> None:
        v = ImageVariant(
            name="thumb",
            storage_key=StorageKey("ab/cd/x__thumb.png"),
            width=256,
            height=192,
            size_bytes=1234,
        )
        assert v.name == "thumb"

    def test_rejects_bad_dimensions(self) -> None:
        with pytest.raises(ValidationError):
            ImageVariant(
                name="thumb",
                storage_key=StorageKey("ab/cd/x.png"),
                width=0,
                height=10,
                size_bytes=1,
            )
