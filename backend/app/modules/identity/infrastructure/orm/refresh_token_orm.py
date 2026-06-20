"""ORM for the ``refresh_tokens`` whitelist with rotation chains."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.sql import func

from app.shared.infrastructure.db import Base


class RefreshTokenOrm(Base):
    __tablename__ = "refresh_tokens"

    id = Column(BigInteger, primary_key=True)
    public_id = Column(SQL_UUID(as_uuid=True), nullable=False, unique=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(128), nullable=False, unique=True)
    status = Column(
        SAEnum("active", "rotated", "revoked", name="token_status"),
        nullable=False,
        server_default="active",
    )
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by = Column(
        BigInteger,
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_agent = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)

    __table_args__ = (Index("ix_refresh_tokens_user_status", "user_id", "status"),)
