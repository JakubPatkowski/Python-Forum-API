"""Unit tests for the materialized path / depth logic.

These tests verify the domain-only invariants — no DB. The path's tail
segment is otherwise assigned by the repository after INSERT.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.content.domain.comment import (
    PATH_SEGMENT_WIDTH,
    PATH_SEPARATOR,
    Comment,
    depth_of_path,
    encode_path_segment,
    path_for,
)
from app.modules.content.domain.post import PostId
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
)
from app.modules.identity.domain.user import UserId
from app.shared.domain.errors import ValidationError


def _body(text: str = "Hello") -> MarkdownContent:
    return MarkdownContent(body=text, format=ContentFormat.MARKDOWN)


class TestEncodePathSegment:
    def test_pads_to_fixed_width(self) -> None:
        assert encode_path_segment(1) == "0" * (PATH_SEGMENT_WIDTH - 1) + "1"
        assert encode_path_segment(42) == "0" * (PATH_SEGMENT_WIDTH - 2) + "42"

    def test_rejects_negative_id(self) -> None:
        with pytest.raises(ValueError):
            encode_path_segment(-1)

    def test_does_not_truncate_large_ids(self) -> None:
        # Beyond the padded width the segment grows. Depth counting still
        # relies on the separator, not segment width.
        assert encode_path_segment(10**9) == str(10**9)


class TestPathFor:
    def test_top_level_path_is_just_segment(self) -> None:
        assert path_for(None, 7) == encode_path_segment(7)

    def test_nested_path_appends_dot_segment(self) -> None:
        parent = encode_path_segment(3)
        assert path_for(parent, 9) == f"{parent}{PATH_SEPARATOR}{encode_path_segment(9)}"


class TestDepthOfPath:
    def test_empty_path_is_depth_zero(self) -> None:
        assert depth_of_path("") == 0

    def test_top_level_is_depth_zero(self) -> None:
        assert depth_of_path(encode_path_segment(1)) == 0

    def test_each_segment_after_root_adds_one(self) -> None:
        # Build a 3-segment path: root.child.grandchild
        p = ".".join(encode_path_segment(i) for i in (1, 2, 3))
        assert depth_of_path(p) == 2


class TestCommentCreate:
    def test_top_level_comment_has_depth_zero_and_no_parent(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        comment = Comment.create(
            post_id=post_id,
            author_id=author,
            content=_body(),
        )
        assert comment.depth == 0
        assert comment.parent_id is None
        # Path is empty until the repository assigns it.
        assert comment.path == ""

    def test_reply_increments_depth_and_records_parent(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        parent = Comment.create(
            post_id=post_id,
            author_id=author,
            content=_body(),
        )
        parent.assign_path(db_id=1, parent_path=None)
        reply = Comment.create(
            post_id=post_id,
            author_id=author,
            content=_body("reply"),
            parent=parent,
        )
        assert reply.depth == 1
        assert reply.parent_id == parent.id

    def test_max_depth_blocks_deeper_replies(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        current = Comment.create(
            post_id=post_id, author_id=author, content=_body(), max_depth=2
        )
        deeper = Comment.create(
            post_id=post_id,
            author_id=author,
            content=_body(),
            parent=current,
            max_depth=2,
        )
        with pytest.raises(ValidationError):
            Comment.create(
                post_id=post_id,
                author_id=author,
                content=_body(),
                parent=deeper,
                max_depth=2,
            )

    def test_reply_rejected_if_parent_belongs_to_different_post(self) -> None:
        post_a = PostId(uuid4())
        post_b = PostId(uuid4())
        author = UserId(uuid4())
        parent = Comment.create(
            post_id=post_a, author_id=author, content=_body()
        )
        with pytest.raises(ValidationError):
            Comment.create(
                post_id=post_b,
                author_id=author,
                content=_body(),
                parent=parent,
            )


class TestAssignPath:
    def test_top_level_path_assignment(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        c = Comment.create(post_id=post_id, author_id=author, content=_body())
        c.assign_path(db_id=42, parent_path=None)
        assert c.path == encode_path_segment(42)

    def test_nested_path_assignment(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        c = Comment.create(post_id=post_id, author_id=author, content=_body())
        parent_path = encode_path_segment(3)
        c.assign_path(db_id=42, parent_path=parent_path)
        assert c.path == f"{parent_path}.{encode_path_segment(42)}"


class TestSoftDelete:
    def test_replaces_body_and_marks_deleted(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        c = Comment.create(
            post_id=post_id, author_id=author, content=_body("original")
        )
        c.soft_delete(deleted_by=author)
        assert c.is_deleted is True
        assert c.content.body == "[deleted]"

    def test_idempotent(self) -> None:
        post_id = PostId(uuid4())
        author = UserId(uuid4())
        c = Comment.create(
            post_id=post_id, author_id=author, content=_body("once")
        )
        c.soft_delete(deleted_by=author)
        # Second call must not change content or emit a duplicate event.
        events_before = len(c.pull_events())
        c.soft_delete(deleted_by=author)
        assert c.content.body == "[deleted]"
        # ``pull_events`` empties the buffer; a no-op delete should not refill it.
        assert c.pull_events() == []
        assert events_before >= 1
