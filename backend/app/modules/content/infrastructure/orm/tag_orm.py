"""ORM for ``tags`` and the M:N ``post_tags`` link table (phase 2).

Both tables are *new* in phase 2 — neither has a legacy counterpart — so
the mapping lives entirely in this module.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.sql import func

from app.shared.infrastructure.db import Base


class TagOrm(Base):
    """A short, lowercase label attached to one or more posts.

    Names are unique at the DB level; the canonical form is lowercase. A
    ``slug`` column carries the URL-safe form for ``GET /tags/{slug}``.
    """

    __tablename__ = "tags"

    id = Column(BigInteger, primary_key=True)
    public_id = Column(SQL_UUID(as_uuid=True), unique=True, nullable=False, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    slug = Column(String(60), unique=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PostTagOrm(Base):
    """Association table ``post_tags`` — M:N between posts and tags."""

    __tablename__ = "post_tags"

    post_id = Column(
        Integer,
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(
        BigInteger,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
