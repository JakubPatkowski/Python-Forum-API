"""Unit tests for the Post aggregate root.

Covers the factory, partial-edit semantics (only changed fields emit an
event), soft-delete idempotency, title validation and format switching.
"""

from __future__ import annotations

import pytest

from app.modules.content.domain.category import CategoryId
from app.modules.content.domain.events import (
    PostCreated,
    PostDeleted,
    PostUpdated,
)
from app.modules.content.domain.post import Post
from app.modules.content.domain.tag import Tag
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
    Slug,
)
from app.modules.identity.domain.user import UserId
from app.shared.domain.errors import ValidationError


def _content(body: str = "A body long enough.") -> MarkdownContent:
    return MarkdownContent(body=body, format=ContentFormat.MARKDOWN)


def _make_post(**overrides: object) -> Post:
    kwargs: dict[str, object] = {
        "author_id": UserId.new(),
        "title": "A valid title",
        "content": _content(),
    }
    kwargs.update(overrides)
    return Post.create(**kwargs)  # type: ignore[arg-type]


class TestCreate:
    def test_derives_slug_from_title_and_records_event(self) -> None:
        post = _make_post(title="Najlepsze Łowiska w Polsce")
        assert post.slug.value == "najlepsze-lowiska-w-polsce"
        events = post.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], PostCreated)
        assert events[0].slug == "najlepsze-lowiska-w-polsce"

    def test_strips_title_whitespace(self) -> None:
        post = _make_post(title="   Trimmed title   ")
        assert post.title == "Trimmed title"

    def test_explicit_slug_overrides_derivation(self) -> None:
        post = _make_post(title="Whatever", slug=Slug("custom-slug"))
        assert post.slug.value == "custom-slug"

    def test_carries_category_and_tags(self) -> None:
        cat = CategoryId.new()
        tags = {Tag.create("spinning"), Tag.create("karp")}
        post = _make_post(category_id=cat, tags=tags)
        assert post.category_id == cat
        assert post.tags == frozenset(tags)

    @pytest.mark.parametrize("title", ["", "  ", "ab", "x" * 201])
    def test_rejects_invalid_title(self, title: str) -> None:
        with pytest.raises(ValidationError):
            _make_post(title=title)


class TestEdit:
    def test_changing_title_updates_slug_only_when_passed(self) -> None:
        post = _make_post(title="Original title")
        post.pull_events()
        new_slug = Slug.from_text("Brand new title")
        post.edit(title="Brand new title", slug=new_slug)
        assert post.title == "Brand new title"
        assert post.slug.value == "brand-new-title"
        events = post.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], PostUpdated)

    def test_no_op_edit_records_no_event(self) -> None:
        post = _make_post(title="Same title", content=_content("Same body here."))
        post.pull_events()
        # Pass identical values — nothing actually changes.
        post.edit(title="Same title", content=_content("Same body here."))
        assert post.pull_events() == []

    def test_partial_edit_touches_updated_at(self) -> None:
        post = _make_post()
        before = post.updated_at
        post.edit(content=_content("A different body entirely."))
        assert post.updated_at >= before

    def test_edit_records_updated_by(self) -> None:
        post = _make_post()
        post.pull_events()
        actor = UserId.new()
        post.edit(title="A changed title", updated_by=actor)
        event = post.pull_events()[0]
        assert isinstance(event, PostUpdated)
        assert event.updated_by == actor.value

    def test_cannot_edit_deleted_post(self) -> None:
        post = _make_post()
        post.soft_delete()
        with pytest.raises(ValidationError):
            post.edit(title="too late")

    def test_edit_rejects_invalid_new_title(self) -> None:
        post = _make_post()
        with pytest.raises(ValidationError):
            post.edit(title="x")


class TestSoftDelete:
    def test_marks_deleted_and_records_event(self) -> None:
        post = _make_post()
        post.pull_events()
        actor = UserId.new()
        post.soft_delete(deleted_by=actor)
        assert post.is_deleted is True
        event = post.pull_events()[0]
        assert isinstance(event, PostDeleted)
        assert event.deleted_by == actor.value

    def test_idempotent(self) -> None:
        post = _make_post()
        post.soft_delete()
        post.pull_events()
        post.soft_delete()
        assert post.pull_events() == []


class TestSetFormat:
    def test_switches_format(self) -> None:
        post = _make_post()
        assert post.content.format == ContentFormat.MARKDOWN
        post.set_format(ContentFormat.PLAIN)
        assert post.content.format == ContentFormat.PLAIN
        # body is preserved
        assert post.content.body == "A body long enough."

    def test_same_format_is_no_op(self) -> None:
        post = _make_post()
        before = post.updated_at
        post.set_format(ContentFormat.MARKDOWN)
        assert post.updated_at == before
