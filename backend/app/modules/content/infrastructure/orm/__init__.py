"""SQLAlchemy ORM mappings for the content module.

Re-exports the existing :class:`PostOrm`, :class:`CommentOrm`, and
:class:`CategoryOrm` shared with the legacy code (see ``app.models``), plus
the new ``tags`` and ``post_tags`` tables introduced in phase 2.
"""

from app.modules.content.infrastructure.orm.category_orm import CategoryOrm
from app.modules.content.infrastructure.orm.comment_orm import CommentOrm
from app.modules.content.infrastructure.orm.post_orm import PostOrm
from app.modules.content.infrastructure.orm.tag_orm import (
    PostTagOrm,
    TagOrm,
)

__all__ = [
    "CategoryOrm",
    "CommentOrm",
    "PostOrm",
    "PostTagOrm",
    "TagOrm",
]
