"""ORM ↔ Domain mappers for the content module.

Pure functions that translate SQLAlchemy rows to domain aggregates / value
objects. Repositories call these to keep their methods small and easy to
read.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.content.application.commands import (
    AuthorSummary,
    CategorySummary,
    CommentSummary,
    PostSummary,
    TagSummary,
)
from app.modules.content.domain.category import Category, CategoryId
from app.modules.content.domain.comment import Comment, CommentId
from app.modules.content.domain.post import Post, PostId
from app.modules.content.domain.tag import Tag, TagId
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
    Slug,
)
from app.modules.identity.domain.user import UserId

# --------------------------------------------------------------------------- #
# Time helpers — Postgres returns timezone-aware datetimes from columns with  #
# ``timezone=True``; the legacy posts/comments tables still use naive UTC.    #
# --------------------------------------------------------------------------- #


def _aware(value: datetime | None) -> datetime:
    """Coerce a possibly-naive ``datetime`` to UTC-aware. Defaults to ``now``."""
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# --------------------------------------------------------------------------- #
# Category                                                                    #
# --------------------------------------------------------------------------- #


def category_from_orm(row) -> Category:
    """Hydrate a :class:`Category` aggregate from a ``categories`` row."""
    assert row.public_id is not None, "Category row missing public_id"
    assert row.slug is not None, "Category row missing slug"
    return Category(
        id=CategoryId(row.public_id),
        name=row.name,
        slug=Slug(row.slug),
        description=row.description,
        created_at=_aware(row.created_at),
    )


def category_summary_from_orm(row) -> CategorySummary:
    return CategorySummary(
        public_id=row.public_id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        created_at=_aware(row.created_at),
    )


# --------------------------------------------------------------------------- #
# Tag                                                                          #
# --------------------------------------------------------------------------- #


def tag_from_orm(row) -> Tag:
    return Tag(
        id=TagId(row.public_id),
        name=row.name,
        slug=Slug(row.slug),
    )


def tag_summary_from_orm(row) -> TagSummary:
    return TagSummary(public_id=row.public_id, name=row.name, slug=row.slug)


# --------------------------------------------------------------------------- #
# Post                                                                         #
# --------------------------------------------------------------------------- #


def post_from_orm(
    row,
    *,
    category: Category | None,
    tags: set[Tag],
    author_public_id: UUID,
) -> Post:
    """Build a :class:`Post` aggregate from an ORM row + already-resolved relations."""
    fmt_value = (
        row.content_format.value
        if hasattr(row.content_format, "value")
        else str(row.content_format)
    )
    return Post(
        id=PostId(row.public_id),
        author_id=UserId(author_public_id),
        title=row.title,
        slug=Slug(row.slug),
        content=MarkdownContent(body=row.content, format=ContentFormat(fmt_value)),
        category_id=category.id if category else None,
        tags=set(tags),
        is_deleted=bool(row.is_deleted),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def post_summary_from_row(
    row,
    *,
    author: AuthorSummary,
    category: CategorySummary | None,
    tags: tuple[TagSummary, ...],
    comment_count: int = 0,
) -> PostSummary:
    """Project a post row into the canonical :class:`PostSummary` DTO."""
    fmt_value = (
        row.content_format.value
        if hasattr(row.content_format, "value")
        else str(row.content_format)
    )
    return PostSummary(
        public_id=row.public_id,
        title=row.title,
        slug=row.slug,
        content=row.content,
        content_format=fmt_value,
        author=author,
        category=category,
        tags=tags,
        is_deleted=bool(row.is_deleted),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        comment_count=comment_count,
    )


# --------------------------------------------------------------------------- #
# Comment                                                                      #
# --------------------------------------------------------------------------- #


def comment_from_orm(row, *, author_public_id: UUID | None) -> Comment:
    """Build a :class:`Comment` aggregate from an ORM row."""
    fmt_value = (
        row.content_format.value
        if hasattr(row.content_format, "value")
        else str(row.content_format)
    )
    # Phase-2 stores public_id on the comment row; legacy rows might not have
    # one until migration 0004 backfills them.
    public_id = row.public_id
    assert public_id is not None, "Comment row missing public_id"

    parent_public_id_attr = getattr(row, "_parent_public_id", None)
    parent_id = (
        CommentId(parent_public_id_attr) if parent_public_id_attr else None
    )

    return Comment(
        id=CommentId(public_id),
        post_id=PostId(row._post_public_id),
        author_id=UserId(author_public_id) if author_public_id else None,
        parent_id=parent_id,
        content=MarkdownContent(
            body=row.content, format=ContentFormat(fmt_value)
        ),
        depth=row.depth or 0,
        path=row.path or "",
        is_deleted=bool(row.is_deleted),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def comment_summary_from_row(
    row,
    *,
    post_public_id: UUID,
    parent_public_id: UUID | None,
    author: AuthorSummary,
) -> CommentSummary:
    fmt_value = (
        row.content_format.value
        if hasattr(row.content_format, "value")
        else str(row.content_format)
    )
    return CommentSummary(
        public_id=row.public_id,
        post_public_id=post_public_id,
        parent_public_id=parent_public_id,
        depth=row.depth or 0,
        path=row.path or "",
        content=row.content,
        content_format=fmt_value,
        is_deleted=bool(row.is_deleted),
        author=author,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )
