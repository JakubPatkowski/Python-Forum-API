"""Domain events emitted by the content aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class PostCreated(DomainEvent):
    post_id: UUID
    author_id: UUID
    title: str
    slug: str
    category_id: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PostUpdated(DomainEvent):
    post_id: UUID
    author_id: UUID
    updated_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PostDeleted(DomainEvent):
    post_id: UUID
    author_id: UUID
    deleted_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CommentAdded(DomainEvent):
    comment_id: UUID
    post_id: UUID
    author_id: UUID | None
    parent_comment_id: UUID | None = None
    depth: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class CommentUpdated(DomainEvent):
    comment_id: UUID
    post_id: UUID
    updated_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CommentDeleted(DomainEvent):
    """Soft-delete event — the row stays so the tree keeps its structure."""

    comment_id: UUID
    post_id: UUID
    deleted_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryCreated(DomainEvent):
    category_id: UUID
    name: str
    slug: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryDeleted(DomainEvent):
    category_id: UUID
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TagCreated(DomainEvent):
    tag_id: UUID
    name: str
    slug: str
