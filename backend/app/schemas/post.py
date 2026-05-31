from datetime import datetime

from pydantic import BaseModel, Field

from app.models.post import ContentFormat
from app.schemas.user import UserOut


class PostCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=1, max_length=50_000)
    content_format: ContentFormat = ContentFormat.MARKDOWN
    category_id: int | None = None


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=50_000)
    content_format: ContentFormat | None = None
    category_id: int | None = None


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    content_format: ContentFormat
    created_at: datetime
    updated_at: datetime
    author: UserOut
    category_id: int | None

    model_config = {"from_attributes": True}
