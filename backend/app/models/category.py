from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Category(Base):
    """``categories`` table — shared ORM mapping (legacy + phase-2 columns).

    Phase-2 additions: ``public_id`` (UUID for API), ``slug`` (URL fragment)
    and ``created_at``. The legacy ``id``/``name``/``description`` columns
    stay because the admin SSR routes still use them.
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    # --- phase-2 (content module v3) ---------------------------------------
    public_id = Column(SQL_UUID(as_uuid=True), unique=True, nullable=True, index=True)
    slug = Column(String(120), unique=True, nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )

    posts = relationship("Post", back_populates="category")
