from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, Enum):
    """Hierarchia ról: ADMIN > MODERATOR > USER."""

    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(
        SAEnum(UserRole, name="user_role"),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
