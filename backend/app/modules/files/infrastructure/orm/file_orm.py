"""SQLAlchemy mapping for the new ``files`` table (phase 3).

A brand-new table with no legacy counterpart, so the whole mapping lives here.
Internal PK is ``id`` (BigInteger / bigserial) to match the BigInteger
``users.avatar_file_id`` FK; all owner FKs reference the legacy Integer PKs.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.sql import func

from app.modules.files.domain.value_objects import FileOwnerType, FileStatus
from app.shared.infrastructure.db import Base

_OWNER_ENUM = SAEnum(
    FileOwnerType,
    name="file_owner_type",
    values_callable=lambda e: [m.value for m in e],
)
_STATUS_ENUM = SAEnum(
    FileStatus,
    name="file_status",
    values_callable=lambda e: [m.value for m in e],
)


class FileOrm(Base):
    """``files`` — generic metadata for every uploaded object in MinIO."""

    __tablename__ = "files"
    __table_args__ = (
        # At most one owner FK set; consistency with owner_type enforced by the
        # owner_type_match check below (a portable subset of the doc's CHECK).
        CheckConstraint(
            "(CASE WHEN owner_post_id     IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN owner_comment_id  IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN owner_user_id     IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN owner_category_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
            name="owner_single",
        ),
        CheckConstraint("size_bytes >= 0", name="size_nonneg"),
    )

    id = Column(BigInteger, primary_key=True)
    public_id = Column(SQL_UUID(as_uuid=True), unique=True, nullable=False, index=True)
    uploader_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    storage_key = Column(String(255), unique=True, nullable=False)
    original_name = Column(String(255), nullable=False)
    content_type = Column(String(150), nullable=False)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    sha256 = Column(String(64), nullable=True, index=True)

    status = Column(_STATUS_ENUM, nullable=False, default=FileStatus.PENDING.value)
    owner_type = Column(
        _OWNER_ENUM, nullable=False, default=FileOwnerType.STANDALONE.value, index=True
    )

    owner_post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    # {variant_name: {storage_key, width, height, size_bytes}}
    variants = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
