"""Pydantic request / response DTOs for the post endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.application.commands import (
    CategorySummary,
    CreatePostCommand,
    PostListPage,
    PostSummary,
    TagSummary,
    UpdatePostCommand,
)

# --------------------------------------------------------------------------- #
# Request DTOs                                                                #
# --------------------------------------------------------------------------- #


class CreatePostRequest(BaseModel):
    """Payload accepted by ``POST /api/v1/posts``."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=3, max_length=200)]
    content: Annotated[str, Field(min_length=1)]
    content_format: Annotated[str, Field(pattern="^(plain|markdown)$")] = "markdown"
    category_id: UUID | None = None
    tags: list[str] = Field(default_factory=list, max_length=10)

    def to_command(self, *, author_public_id: UUID) -> CreatePostCommand:
        return CreatePostCommand(
            author_public_id=author_public_id,
            title=self.title,
            content=self.content,
            content_format=self.content_format,
            category_public_id=self.category_id,
            tag_names=tuple(self.tags),
        )


class UpdatePostRequest(BaseModel):
    """Payload accepted by ``PUT /api/v1/posts/{id}``. All fields optional."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=3, max_length=200)] | None = None
    content: str | None = None
    content_format: Annotated[str, Field(pattern="^(plain|markdown)$")] | None = None
    category_id: UUID | None = None
    tags: list[str] | None = Field(default=None, max_length=10)

    def to_command(
        self,
        *,
        post_public_id: UUID,
        actor_public_id: UUID,
        actor_can_moderate: bool,
    ) -> UpdatePostCommand:
        return UpdatePostCommand(
            post_public_id=post_public_id,
            actor_public_id=actor_public_id,
            title=self.title,
            content=self.content,
            content_format=self.content_format,
            category_public_id=self.category_id,
            tag_names=tuple(self.tags) if self.tags is not None else None,
            actor_can_moderate=actor_can_moderate,
        )


# --------------------------------------------------------------------------- #
# Response DTOs                                                               #
# --------------------------------------------------------------------------- #


class AuthorResponse(BaseModel):
    public_id: UUID | None
    username: str | None


class CategoryRefResponse(BaseModel):
    public_id: UUID
    name: str
    slug: str

    @classmethod
    def from_summary(cls, c: CategorySummary) -> CategoryRefResponse:
        return cls(public_id=c.public_id, name=c.name, slug=c.slug)


class TagRefResponse(BaseModel):
    public_id: UUID
    name: str
    slug: str

    @classmethod
    def from_summary(cls, t: TagSummary) -> TagRefResponse:
        return cls(public_id=t.public_id, name=t.name, slug=t.slug)


class PostResponse(BaseModel):
    """Public projection of a single post."""

    id: UUID
    title: str
    slug: str
    content: str
    content_format: str
    author: AuthorResponse
    category: CategoryRefResponse | None
    tags: list[TagRefResponse]
    is_deleted: bool
    comment_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(cls, s: PostSummary) -> PostResponse:
        return cls(
            id=s.public_id,
            title=s.title,
            slug=s.slug,
            content=s.content,
            content_format=s.content_format,
            author=AuthorResponse(
                public_id=s.author.public_id, username=s.author.username
            ),
            category=(
                CategoryRefResponse.from_summary(s.category)
                if s.category
                else None
            ),
            tags=[TagRefResponse.from_summary(t) for t in s.tags],
            is_deleted=s.is_deleted,
            comment_count=s.comment_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class PostListResponse(BaseModel):
    """A page of posts with the opaque keyset cursor for the next page."""

    items: list[PostResponse]
    next_cursor: str | None

    @classmethod
    def from_page(cls, p: PostListPage) -> PostListResponse:
        return cls(
            items=[PostResponse.from_summary(s) for s in p.items],
            next_cursor=p.next_cursor,
        )
