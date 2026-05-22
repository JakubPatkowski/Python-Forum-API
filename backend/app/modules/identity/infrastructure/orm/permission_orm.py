"""ORM for the ``permissions`` catalogue table."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, String, Text

from app.shared.infrastructure.db import Base


class PermissionOrm(Base):
    __tablename__ = "permissions"

    id = Column(BigInteger, primary_key=True)
    code = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
