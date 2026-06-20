"""SQLAlchemy mapping for ``users``.

The legacy class :class:`app.models.user.User` already maps the table and
keeps the legacy ``role``/``is_active`` columns alive for content/files
routers that have not yet been migrated. We re-export it as ``UserOrm``
so the new identity code reads cleanly while remaining compatible.

Once phases 2 and 3 retire those legacy columns, the mapping can move
here in full and ``app.models.user`` will be deleted.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func

from app.models.user import User as _LegacyUserModel
from app.shared.infrastructure.db import Base

# Public alias — phase-1 code should refer to this name only.
UserOrm = _LegacyUserModel


class UserRoleOrm(Base):
    """Association table ``user_roles`` — M:N between users and roles."""

    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    granted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    granted_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class UserPermissionOrm(Base):
    """Per-user override of a permission code (allow/deny)."""

    __tablename__ = "user_permissions"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    granted = Column(Boolean, nullable=False)
    granted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    granted_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
