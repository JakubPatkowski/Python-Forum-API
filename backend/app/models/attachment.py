from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Attachment(Base):
    """Metadane pliku zalaczonego do posta lub komentarza.

    Plik fizycznie lezy na dysku w `settings.UPLOAD_DIR / stored_filename`.
    Polimorficzny: dokladnie jedno z (post_id, comment_id) musi byc ustawione.
    """

    __tablename__ = "attachments"
    __table_args__ = (
        # XOR portable miedzy Postgres i SQLite
        CheckConstraint(
            "(CASE WHEN post_id IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN comment_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="attachment_owner_xor",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), unique=True, nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(
        Integer,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    uploader = relationship("User", back_populates="attachments")
    post = relationship("Post", back_populates="attachments", foreign_keys=[post_id])
    comment = relationship(
        "Comment", back_populates="attachments", foreign_keys=[comment_id]
    )
