"""ORM for ``roles`` and the M:N ``role_permissions`` link table."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text

from app.shared.infrastructure.db import Base


class RoleOrm(Base):
    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)


class RolePermissionOrm(Base):
    __tablename__ = "role_permissions"

    role_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = Column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
