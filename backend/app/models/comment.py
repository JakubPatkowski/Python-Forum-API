from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.post import ContentFormat


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    content_format = Column(
        SAEnum(ContentFormat, name="content_format", values_callable=lambda e: [m.value for m in e]),
        default=ContentFormat.MARKDOWN,
        nullable=False,
    )
    # Self-FK do zagnieżdżania
    parent_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Cache stopnia zagnieżdżenia (0 = top-level). Walidowane w warstwie service.
    depth = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)

    author = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")

    # Self-relation. `remote_side=[id]` — po stronie rodzica.
    parent = relationship("Comment", remote_side=[id], back_populates="children")
    children = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )

    attachments = relationship(
        "Attachment",
        back_populates="comment",
        cascade="all, delete-orphan",
        foreign_keys="Attachment.comment_id",
    )
