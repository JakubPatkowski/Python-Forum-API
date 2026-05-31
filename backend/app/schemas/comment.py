from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.post import ContentFormat
from app.schemas.user import UserOut


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    content_format: ContentFormat = ContentFormat.MARKDOWN
    post_id: int
    parent_id: int | None = None


class CommentUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10_000)
    content_format: ContentFormat | None = None


class CommentOut(BaseModel):
    """Pojedynczy komentarz BEZ dzieci — używane np. w odpowiedziach po POST."""

    id: int
    content: str
    content_format: ContentFormat
    created_at: datetime
    author: UserOut
    post_id: int
    parent_id: int | None
    depth: int

    model_config = {"from_attributes": True}


class CommentTreeOut(CommentOut):
    """Wariant rekurencyjny — z polem `children` (lista poddrzew)."""

    children: list[CommentTreeOut] = Field(default_factory=list)


# Pydantic v2 — model self-referencyjny działa przez ForwardRef + rebuild.
CommentTreeOut.model_rebuild()
