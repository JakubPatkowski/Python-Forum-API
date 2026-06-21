"""Unit tests for the Category entity and Tag entity factories."""

from __future__ import annotations

import pytest

from app.modules.content.domain.category import Category, CategoryId
from app.modules.content.domain.tag import Tag
from app.modules.content.domain.value_objects import Slug
from app.shared.domain.errors import ValidationError


def _category(name: str = "Spinning") -> Category:
    return Category(id=CategoryId.new(), name=name, slug=Slug.from_text(name))


class TestCategory:
    def test_exposes_name_and_slug(self) -> None:
        cat = _category("Karpiowanie")
        assert cat.name == "Karpiowanie"
        assert cat.slug.value == "karpiowanie"

    def test_rename_updates_name_and_trims(self) -> None:
        cat = _category()
        cat.rename("  Muszka  ")
        assert cat.name == "Muszka"
        # slug not changed when not provided
        assert cat.slug.value == "spinning"

    def test_rename_can_update_slug(self) -> None:
        cat = _category()
        cat.rename("Muszka", slug=Slug.from_text("Muszka"))
        assert cat.slug.value == "muszka"

    @pytest.mark.parametrize("name", ["", "   "])
    def test_rename_rejects_blank(self, name: str) -> None:
        cat = _category()
        with pytest.raises(ValidationError):
            cat.rename(name)


class TestTag:
    def test_create_lowercases_and_derives_slug(self) -> None:
        tag = Tag.create("  SpinningLures  ")
        assert tag.name == "spinninglures"
        assert tag.slug.value == "spinninglures"

    def test_create_rejects_blank(self) -> None:
        with pytest.raises(ValidationError):
            Tag.create("   ")

    def test_create_rejects_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Tag.create("x" * 51)

    def test_create_accepts_max_length(self) -> None:
        tag = Tag.create("a" * 50)
        assert len(tag.name) == 50

    def test_equality_is_by_identity(self) -> None:
        # Two tags built from the same name still get different ids -> not equal.
        a = Tag.create("karp")
        b = Tag.create("karp")
        assert a != b
        assert a == Tag(id=a.id, name=a.name, slug=a.slug)  # equality is by id
