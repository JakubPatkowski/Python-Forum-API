"""Pydantic request / response DTOs for the comment endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.application.commands import (
    AddCommentCommand,
    CommentSummary,
    UpdateCommentCommand,
)


class AddCommentRequest(BaseModel):
    """Payload accepted by ``POST /api/v1/comments``."""

    model_config = ConfigDict(extra="forbid")

    post_id: UUID
    content: Annotated[str, Field(min_length=1)]
    content_format: Annotated[str, Field(pattern="^(plain|markdown)$")] = "markdown"
    parent_id: UUID | None = None

    def to_command(self, *, author_public_id: UUID) -> AddCommentCommand:
        return AddCommentCommand(
            post_public_id=self.post_id,
            author_public_id=author_public_id,
            content=self.content,
            content_format=self.content_format,
            parent_comment_public_id=self.parent_id,
        )


class UpdateCommentRequest(BaseModel):
    """Payload accepted by ``PUT /api/v1/comments/{id}``."""

    model_config = ConfigDict(extra="forbid")

    content: Annotated[str, Field(min_length=1)]
    content_format: Annotated[str, Field(pattern="^(plain|markdown)$")] | None = None

    def to_command(
        self,
        *,
        comment_public_id: UUID,
        actor_public_id: UUID,
        actor_can_moderate: bool,
    ) -> UpdateCommentCommand:
        return UpdateCommentCommand(
            comment_public_id=comment_public_id,
            actor_public_id=actor_public_id,
            content=self.content,
            content_format=self.content_format,
            actor_can_moderate=actor_can_moderate,
        )


class CommentAuthorResponse(BaseModel):
    public_id: UUID | None
    username: str | None


class CommentResponse(BaseModel):
    """Public projection of a single comment.

    ``depth`` and ``path`` are exposed so the frontend can reconstruct the
    tree client-side from the flat DFS list returned by the tree endpoint.
    """

    id: UUID
    post_id: UUID
    parent_id: UUID | None
    depth: int
    path: str
    content: str
    content_format: str
    is_deleted: bool
    author: CommentAuthorResponse
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(cls, s: CommentSummary) -> CommentResponse:
        return cls(
            id=s.public_id,
            post_id=s.post_public_id,
            parent_id=s.parent_public_id,
            depth=s.depth,
            path=s.path,
            content=s.content,
            content_format=s.content_format,
            is_deleted=s.is_deleted,
            author=CommentAuthorResponse(public_id=s.author.public_id, username=s.author.username),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class CommentTreeResponse(BaseModel):
    """A post's full comment tree in DFS order."""

    items: list[CommentResponse]

    @classmethod
    def from_summaries(cls, items: list[CommentSummary]) -> CommentTreeResponse:
        return cls(items=[CommentResponse.from_summary(c) for c in items])
