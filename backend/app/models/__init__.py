"""Eksport wszystkich modeli — kolejność ważna dla SQLAlchemy mapper config."""
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.post import ContentFormat, Post
from app.models.comment import Comment

# Attachment model removed in phase 3 — uploads now live in the modular
# ``files`` table (app.modules.files).

__all__ = [
    "User",
    "UserRole",
    "Category",
    "Post",
    "ContentFormat",
    "Comment",
]
