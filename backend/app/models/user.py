from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, Enum):
    """Hierarchia ról: ADMIN > MODERATOR > USER.

    Legacy enum — phase 1 introduces a proper RBAC (tables ``roles``,
    ``role_permissions``, ``user_roles``). This column is kept until
    legacy posts/comments/attachments routers are retired in phases 2-3.
    """

    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """Lifecycle status of a user account (phase 1 RBAC)."""

    ACTIVE = "active"
    BLOCKED = "blocked"
    PENDING_VERIFICATION = "pending_verification"


class User(Base):
    """``users`` table — single ORM mapping shared by legacy and phase-1 code.

    Legacy columns (``hashed_password``, ``is_active``, ``role``) coexist with
    phase-1 columns (``public_id``, ``password_hash``, ``status``,
    ``avatar_file_id``, ``updated_at``). New registrations populate both
    sets so legacy routers keep functioning until they're removed.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Phase-1 public identifier — exposed in JWT ``sub`` and API URLs.
    public_id = Column(SQL_UUID(as_uuid=True), unique=True, nullable=True, index=True)

    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)

    # --- legacy auth (phase 0) ---------------------------------------------
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(
        SAEnum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- phase-1 auth (Argon2 hash, status enum, avatar, updated_at) -------
    password_hash = Column(String(255), nullable=True)
    status = Column(
        SAEnum(UserStatus, name="user_status", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    avatar_file_id = Column(BigInteger, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    attachments = relationship(
        "Attachment", back_populates="uploader", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        """Backward-compatible alias — niektóre routery sprawdzają is_admin."""
        return self.role == UserRole.ADMIN

    @property
    def is_moderator_or_higher(self) -> bool:
        return self.role in (UserRole.MODERATOR, UserRole.ADMIN)
