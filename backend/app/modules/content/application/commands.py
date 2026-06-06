"""Command and query DTOs consumed by content use cases.

All inputs are framework-agnostic dataclasses. Pydantic request bodies in
the presentation layer map *into* these commands; outputs are projected
into Pydantic responses through the dedicated ``*Summary`` dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

# --------------------------------------------------------------------------- #
# Post commands                                                               #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CreatePostCommand:
    author_public_id: UUID
    title: str
    content: str
    content_format: str = "markdown"
    category_public_id: UUID | None = None
    tag_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class UpdatePostCommand:
    post_public_id: UUID
    actor_public_id: UUID
    title: str | None = None
    content: str | None = None
    content_format: str | None = None
    category_public_id: UUID | None = None
    tag_names: tuple[str, ...] | None = None
    actor_can_moderate: bool = False


@dataclass(frozen=True, slots=True)
class DeletePostCommand:
    post_public_id: UUID
    actor_public_id: UUID
    actor_can_moderate: bool = False


@dataclass(frozen=True, slots=True)
class ListPostsQuery:
    cursor: str | None = None
    limit: int = 20
    category_public_id: UUID | None = None
    tag_slug: str | None = None
    author_public_id: UUID | None = None


# --------------------------------------------------------------------------- #
# Comment commands                                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AddCommentCommand:
    post_public_id: UUID
    author_public_id: UUID
    content: str
    content_format: str = "markdown"
    parent_comment_public_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdateCommentCommand:
    comment_public_id: UUID
    actor_public_id: UUID
    content: str
    content_format: str | None = None
    actor_can_moderate: bool = False


@dataclass(frozen=True, slots=True)
class DeleteCommentCommand:
    comment_public_id: UUID
    actor_public_id: UUID
    actor_can_moderate: bool = False


@dataclass(frozen=True, slots=True)
class GetCommentTreeQuery:
    post_public_id: UUID


# --------------------------------------------------------------------------- #
# Category / Tag commands                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CreateCategoryCommand:
    name: str
    slug: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteCategoryCommand:
    category_public_id: UUID


@dataclass(frozen=True, slots=True)
class CreateTagCommand:
    name: str


# --------------------------------------------------------------------------- #
# Outputs                                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AuthorSummary:
    """Lightweight projection of the author of a post or comment.

    The content module never hydrates a full :class:`User` aggregate — it
    only joins on ``users`` to read ``username`` and ``public_id``.
    """

    public_id: UUID | None
    username: str | None


@dataclass(frozen=True, slots=True)
class TagSummary:
    public_id: UUID
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class CategorySummary:
    public_id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PostSummary:
    """The canonical projection of a Post returned by every use case."""

    public_id: UUID
    title: str
    slug: str
    content: str
    content_format: str
    author: AuthorSummary
    category: CategorySummary | None
    tags: tuple[TagSummary, ...]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    comment_count: int = 0


@dataclass(frozen=True, slots=True)
class CommentSummary:
    public_id: UUID
    post_public_id: UUID
    parent_public_id: UUID | None
    depth: int
    path: str
    content: str
    content_format: str
    is_deleted: bool
    author: AuthorSummary
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PostListPage:
    """A page of posts plus an opaque cursor for the next page."""

    items: tuple[PostSummary, ...]
    next_cursor: str | None
