"""Pydantic request / response DTOs for the category endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.application.commands import (
    CategorySummary,
    CreateCategoryCommand,
)


class CreateCategoryRequest(BaseModel):
    """Payload accepted by ``POST /api/v1/categories``."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    slug: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    description: str | None = None

    def to_command(self) -> CreateCategoryCommand:
        return CreateCategoryCommand(
            name=self.name,
            slug=self.slug,
            description=self.description,
        )


class CategoryResponse(BaseModel):
    """Public projection of a category."""

    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    # public UUID of the owner (creator) -- the frontend gates icon editing on it.
    owner_id: UUID | None = None

    @classmethod
    def from_summary(cls, c: CategorySummary, owner_id: UUID | None = None) -> CategoryResponse:
        return cls(
            id=c.public_id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            created_at=c.created_at,
            owner_id=owner_id,
        )
