from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID as SQL_UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ContentFormat(str, Enum):
    """Format treści — używany w postach i komentarzach."""

    PLAIN = "plain"
    MARKDOWN = "markdown"


class Post(Base):
    """``posts`` table — shared ORM mapping for legacy and phase-2 columns.

    Phase-2 additions: ``public_id``, ``slug``, ``is_deleted`` (soft delete)
    and ``search_tsv`` (Postgres full-text vector maintained by a trigger).
    """

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    content_format = Column(
        SAEnum(ContentFormat, name="content_format", values_callable=lambda e: [m.value for m in e]),
        default=ContentFormat.MARKDOWN,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)

    # --- phase-2 (content module v3) ---------------------------------------
    public_id = Column(SQL_UUID(as_uuid=True), unique=True, nullable=True, index=True)
    slug = Column(String(220), nullable=True, index=True)
    is_deleted = Column(Boolean, nullable=False, server_default="false")
    # search_tsv is maintained by a Postgres trigger created in migration 0004.
    search_tsv = Column(TSVECTOR(), nullable=True)

    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")
    comments = relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan"
    )
    # Attachments live in the phase-3 ``files`` module (table ``files``);
    # the legacy ``attachments`` relationship was removed.
    # tag_links — phase-2 (model PostTag jeszcze nie istnieje)
    # tag_links = relationship("PostTag", back_populates="post", cascade="all, delete-orphan")
