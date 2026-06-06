"""Pydantic request / response DTOs for the tag endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.application.commands import CreateTagCommand
from app.modules.content.domain.tag import Tag


class CreateTagRequest(BaseModel):
    """Payload accepted by ``POST /api/v1/tags``."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=50)]

    def to_command(self) -> CreateTagCommand:
        return CreateTagCommand(name=self.name)


class TagResponse(BaseModel):
    """Public projection of a tag."""

    id: UUID
    name: str
    slug: str

    @classmethod
    def from_domain(cls, t: Tag) -> TagResponse:
        return cls(id=t.id.value, name=t.name, slug=str(t.slug))
