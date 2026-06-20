"""Comment aggregate root.

A Comment belongs to a Post and can be a top-level reply or nested under
another Comment. Nesting uses a *materialized path* (zero-padded segments
joined by dots) so subtree queries and DFS ordering work with a single
B-tree index — see ``docs/02-database-schema.md`` §3.

Soft delete (`is_deleted=True`, content replaced) preserves tree shape so
replies do not become orphans.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from app.modules.content.domain.events import (
    CommentAdded,
    CommentDeleted,
    CommentUpdated,
)
from app.modules.content.domain.post import PostId
from app.modules.content.domain.value_objects import MarkdownContent

# UserId is imported by UUID — see note in post.py.
from app.modules.identity.domain.user import UserId
from app.shared.domain.entity import AggregateRoot
from app.shared.domain.entity_id import EntityId
from app.shared.domain.errors import ValidationError

# Path segment width — 8 digits supports IDs up to 99_999_999. Beyond that
# the path is wider; the column accepts 200 chars so depth-8 fits.
PATH_SEGMENT_WIDTH: Final[int] = 8
PATH_SEPARATOR: Final[str] = "."
DELETED_PLACEHOLDER: Final[str] = "[deleted]"


class CommentId(EntityId["Comment"]):
    """Public identifier (UUID) of a :class:`Comment`."""


class Comment(AggregateRoot[CommentId]):
    """A reply attached to a post, optionally nested under another comment."""

    def __init__(
        self,
        *,
        id: CommentId,
        post_id: PostId,
        content: MarkdownContent,
        author_id: UserId | None,
        parent_id: CommentId | None = None,
        depth: int = 0,
        path: str = "",
        is_deleted: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self._post_id = post_id
        self._author_id = author_id
        self._parent_id = parent_id
        self._content = content
        self._depth = depth
        self._path = path
        self._is_deleted = is_deleted
        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    # --- read-only accessors -----------------------------------------------

    @property
    def post_id(self) -> PostId:
        return self._post_id

    @property
    def author_id(self) -> UserId | None:
        return self._author_id

    @property
    def parent_id(self) -> CommentId | None:
        return self._parent_id

    @property
    def content(self) -> MarkdownContent:
        return self._content

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def path(self) -> str:
        return self._path

    @property
    def is_deleted(self) -> bool:
        return self._is_deleted

    # --- factories ----------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        post_id: PostId,
        author_id: UserId | None,
        content: MarkdownContent,
        parent: Comment | None = None,
        max_depth: int = 8,
    ) -> Comment:
        """Factory for a fresh comment.

        Depth and path are seeded from the parent (if any). The repository
        is responsible for assigning the **own** segment of ``path`` once
        it knows the row's serial id — see :meth:`with_path_appended_id`.
        """
        depth = 0 if parent is None else parent.depth + 1
        if depth >= max_depth:
            raise ValidationError(
                f"Comment depth must be less than {max_depth}",
                field="parent_id",
            )
        if parent is not None and parent.post_id != post_id:
            raise ValidationError(
                "Parent comment does not belong to the same post",
                field="parent_id",
            )

        comment = cls(
            id=CommentId.new(),
            post_id=post_id,
            author_id=author_id,
            parent_id=parent.id if parent else None,
            content=content,
            depth=depth,
            path="",  # filled in by the repository after INSERT
        )
        comment.record_event(
            CommentAdded(
                comment_id=comment.id.value,
                post_id=post_id.value,
                author_id=author_id.value if author_id else None,
                parent_comment_id=parent.id.value if parent else None,
                depth=depth,
            )
        )
        return comment

    # --- mutations ----------------------------------------------------------

    def edit(
        self,
        *,
        content: MarkdownContent,
        updated_by: UserId | None = None,
    ) -> None:
        if self._is_deleted:
            raise ValidationError("Cannot edit a deleted comment", field="comment")
        if content == self._content:
            return
        self._content = content
        self._touch()
        self.record_event(
            CommentUpdated(
                comment_id=self.id.value,
                post_id=self._post_id.value,
                updated_by=updated_by.value if updated_by else None,
            )
        )

    def soft_delete(self, *, deleted_by: UserId | None = None) -> None:
        """Mark the comment as deleted; keep the row so the tree stays intact."""
        if self._is_deleted:
            return
        self._is_deleted = True
        # Replace the body so the API can render a "[deleted]" placeholder
        # without the original body leaking.
        self._content = MarkdownContent(body=DELETED_PLACEHOLDER, format=self._content.format)
        self._touch()
        self.record_event(
            CommentDeleted(
                comment_id=self.id.value,
                post_id=self._post_id.value,
                deleted_by=deleted_by.value if deleted_by else None,
            )
        )

    # --- path management ---------------------------------------------------

    def assign_path(self, *, db_id: int, parent_path: str | None) -> None:
        """Set the materialized ``path`` based on the row's integer id.

        Called once by the repository right after INSERT — before that the
        ``id`` segment is unknown. The format is::

            <parent_path>.<own_id_padded>     # nested reply
            <own_id_padded>                   # top-level

        ``db_id`` is the internal ``bigserial`` id from the row. We do not
        leak it back to the domain; only the path string is stored.
        """
        segment = encode_path_segment(db_id)
        if parent_path:
            self._path = f"{parent_path}{PATH_SEPARATOR}{segment}"
        else:
            self._path = segment

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def encode_path_segment(db_id: int) -> str:
    """Format an integer id as a fixed-width, zero-padded path segment."""
    if db_id < 0:
        raise ValueError("Path segment must be non-negative")
    return str(db_id).zfill(PATH_SEGMENT_WIDTH)


def path_for(parent_path: str | None, db_id: int) -> str:
    """Build the materialized path for a comment given the parent's path."""
    segment = encode_path_segment(db_id)
    return f"{parent_path}{PATH_SEPARATOR}{segment}" if parent_path else segment


def depth_of_path(path: str) -> int:
    """Return the depth implied by a materialized ``path``.

    Top-level comments have a single segment → depth ``0``.
    """
    if not path:
        return 0
    return path.count(PATH_SEPARATOR)
