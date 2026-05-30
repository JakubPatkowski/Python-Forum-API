"""Unit tests for content value objects: Slug, MarkdownContent."""

from __future__ import annotations

import pytest

from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
    Slug,
)
from app.shared.domain.errors import ValidationError


class TestSlug:
    def test_accepts_simple_lowercase(self) -> None:
        assert Slug("hello-world").value == "hello-world"

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            " ",
            "Has Uppercase",
            "double--hyphen",
            "-leading",
            "trailing-",
            "with spaces",
            "ÜñîCödé",
        ],
    )
    def test_rejects_malformed(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            Slug(raw)

    def test_from_text_strips_accents_and_lowercases(self) -> None:
        assert Slug.from_text("Łódź Łowienie").value == "lodz-lowienie"

    def test_from_text_truncates(self) -> None:
        s = Slug.from_text("a" * 200, max_length=50)
        assert len(s.value) <= 50

    def test_from_text_rejects_empty_derivation(self) -> None:
        with pytest.raises(ValidationError):
            Slug.from_text("!!!")


class TestMarkdownContent:
    def test_accepts_non_empty_body(self) -> None:
        body = MarkdownContent(body="Hello", format=ContentFormat.MARKDOWN)
        assert body.body == "Hello"
        assert body.format == ContentFormat.MARKDOWN

    @pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
    def test_rejects_blank(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            MarkdownContent(body=raw)

    def test_rejects_too_large(self) -> None:
        with pytest.raises(ValidationError):
            MarkdownContent(body="a" * (64 * 1024 + 1))
