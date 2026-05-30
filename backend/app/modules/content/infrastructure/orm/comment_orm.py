"""SQLAlchemy mapping for ``comments``.

Re-exports the existing :class:`app.models.comment.Comment` so phase-2 code
references a stable ``CommentOrm`` name. Phase-2 added ``public_id``,
``path`` (materialized path) and ``is_deleted`` (soft delete) — see the
legacy class for column definitions and the Alembic migration ``0004`` for
DDL.
"""

from __future__ import annotations

from app.models.comment import Comment as _LegacyCommentModel

# Public alias — phase-2 code should refer to this name only.
CommentOrm = _LegacyCommentModel
