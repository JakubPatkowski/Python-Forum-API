"""SqlAlchemy implementation of :class:`ICommentRepository`.

The repository owns one piece of logic the domain cannot finish on its
own: the materialized ``path``. The path's final segment is the row's
``bigserial`` id, which is only known after INSERT — so the repository
assigns it post-flush and updates the row.

Comment listing for a post is delivered as a flat DFS by ``ORDER BY path``;
the caller reconstructs the tree using ``depth``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post import ContentFormat as LegacyContentFormat
from app.models.user import User as UserOrm
from app.modules.content.application.commands import (
    AuthorSummary,
    CommentSummary,
)
from app.modules.content.application.ports import ICommentRepository
from app.modules.content.domain.comment import (
    Comment,
    CommentId,
    encode_path_segment,
)
from app.modules.content.infrastructure.mappers import (
    comment_from_orm,
    comment_summary_from_row,
)
from app.modules.content.infrastructure.orm import CommentOrm, PostOrm

UserIdResolver = Callable[[UUID], int | None]


class SqlAlchemyCommentRepository(ICommentRepository):
    """Persistence port for :class:`Comment` aggregates."""

    def __init__(
        self,
        session: Session,
        *,
        user_id_resolver: UserIdResolver,
    ) -> None:
        self._session = session
        self._resolve_user_id = user_id_resolver

    # --- read --------------------------------------------------------------

    async def get(self, id_: CommentId) -> Comment | None:
        row = self._session.scalar(select(CommentOrm).where(CommentOrm.public_id == id_.value))
        if row is None:
            return None
        return self._hydrate(row)

    async def exists(self, id_: CommentId) -> bool:
        return (
            self._session.scalar(select(CommentOrm.id).where(CommentOrm.public_id == id_.value))
            is not None
        )

    async def get_with_summary(self, id_: CommentId) -> CommentSummary | None:
        row = self._session.scalar(select(CommentOrm).where(CommentOrm.public_id == id_.value))
        if row is None:
            return None
        return self._project_summary(row)

    async def parent_path_for(self, parent_id: CommentId) -> tuple[str, int] | None:
        row = self._session.execute(
            select(CommentOrm.path, CommentOrm.depth).where(CommentOrm.public_id == parent_id.value)
        ).one_or_none()
        if row is None:
            return None
        return (row[0] or "", row[1] or 0)

    async def list_tree_for_post(self, post_public_id: UUID) -> list[CommentSummary]:
        post_db_id = self._session.scalar(
            select(PostOrm.id).where(PostOrm.public_id == post_public_id)
        )
        if post_db_id is None:
            return []
        rows = self._session.scalars(
            select(CommentOrm)
            .where(CommentOrm.post_id == post_db_id)
            .order_by(CommentOrm.path.asc(), CommentOrm.created_at.asc())
        ).all()
        if not rows:
            return []

        # The post public_id is constant for the whole tree — resolve it once
        # instead of per comment (was one query per row in _project_summary).
        post_public_id_value = self._session.scalar(
            select(PostOrm.public_id).where(PostOrm.id == post_db_id)
        )
        if post_public_id_value is None:
            from uuid import uuid4

            post_public_id_value = uuid4()

        # parent db id -> parent public_id, resolved in a single IN(...) query.
        parent_db_ids = {r.parent_id for r in rows if r.parent_id is not None}
        parent_public_ids: dict[int, UUID] = {}
        if parent_db_ids:
            for cid, public_id in self._session.execute(
                select(CommentOrm.id, CommentOrm.public_id).where(CommentOrm.id.in_(parent_db_ids))
            ).all():
                parent_public_ids[cid] = public_id

        # author db id -> AuthorSummary, resolved in a single IN(...) query.
        author_db_ids = {r.author_id for r in rows if r.author_id is not None}
        authors: dict[int, AuthorSummary] = {}
        if author_db_ids:
            for uid, public_id, username in self._session.execute(
                select(UserOrm.id, UserOrm.public_id, UserOrm.username).where(
                    UserOrm.id.in_(author_db_ids)
                )
            ).all():
                authors[uid] = AuthorSummary(public_id=public_id, username=username)

        return [
            comment_summary_from_row(
                r,
                post_public_id=post_public_id_value,
                parent_public_id=(
                    parent_public_ids.get(cast(int, r.parent_id))
                    if r.parent_id is not None
                    else None
                ),
                author=(
                    authors.get(
                        cast(int, r.author_id),
                        AuthorSummary(public_id=None, username=None),
                    )
                    if r.author_id is not None
                    else AuthorSummary(public_id=None, username=None)
                ),
            )
            for r in rows
        ]

    # --- write -------------------------------------------------------------

    async def add(self, comment: Comment) -> None:
        """Insert a new comment and finalise its path."""
        author_db_id = self._resolve_user_id(comment.author_id.value) if comment.author_id else None
        if comment.author_id and author_db_id is None:
            raise ValueError(f"Unknown comment author {comment.author_id.value}")
        post_db_id = self._session.scalar(
            select(PostOrm.id).where(PostOrm.public_id == comment.post_id.value)
        )
        if post_db_id is None:
            raise ValueError(f"Unknown post {comment.post_id.value}")

        parent_db_id: int | None = None
        parent_path: str = ""
        if comment.parent_id is not None:
            parent_row = self._session.execute(
                select(CommentOrm.id, CommentOrm.path).where(
                    CommentOrm.public_id == comment.parent_id.value
                )
            ).one_or_none()
            if parent_row is None:
                raise ValueError(f"Unknown parent comment {comment.parent_id.value}")
            parent_db_id = parent_row[0]
            parent_path = parent_row[1] or ""

        row = CommentOrm(
            public_id=comment.id.value,
            content=comment.content.body,
            content_format=LegacyContentFormat(comment.content.format.value),
            parent_id=parent_db_id,
            depth=comment.depth,
            post_id=post_db_id,
            author_id=author_db_id,
            is_deleted=comment.is_deleted,
            created_at=comment.created_at.replace(tzinfo=None),
            updated_at=comment.updated_at.replace(tzinfo=None),
            path="",  # placeholder until we know the row id
        )
        self._session.add(row)
        # Flush so the row gets its ``bigserial`` id.
        self._session.flush()

        # Assign the materialized path.
        own_segment = encode_path_segment(row.id)
        row.path = f"{parent_path}.{own_segment}" if parent_path else own_segment
        comment.assign_path(db_id=row.id, parent_path=parent_path or None)
        self._session.flush()

    async def save(self, comment: Comment) -> None:
        """Persist mutations on an already-loaded comment (edit / delete)."""
        row = self._session.scalar(
            select(CommentOrm).where(CommentOrm.public_id == comment.id.value)
        )
        if row is None:
            raise ValueError(f"Comment {comment.id.value} not found")
        row.content = comment.content.body
        row.content_format = LegacyContentFormat(comment.content.format.value)
        row.is_deleted = comment.is_deleted
        row.updated_at = comment.updated_at.replace(tzinfo=None)

    async def remove(self, entity: Comment) -> None:
        self._session.execute(
            CommentOrm.__table__.delete().where(CommentOrm.public_id == entity.id.value)
        )

    # --- helpers ------------------------------------------------------------

    def _hydrate(self, row: CommentOrm) -> Comment:
        # Inject related public_ids onto the row so the mapper can read them
        # without a second query loop.
        post_public_id = self._session.scalar(
            select(PostOrm.public_id).where(PostOrm.id == row.post_id)
        )
        parent_public_id = None
        if row.parent_id is not None:
            parent_public_id = self._session.scalar(
                select(CommentOrm.public_id).where(CommentOrm.id == row.parent_id)
            )
        author_public_id = None
        if row.author_id is not None:
            author_public_id = self._session.scalar(
                select(UserOrm.public_id).where(UserOrm.id == row.author_id)
            )

        # Attach as plain attributes to avoid extending the mapper signature.
        row._post_public_id = post_public_id
        row._parent_public_id = parent_public_id

        return comment_from_orm(row, author_public_id=author_public_id)

    def _project_summary(self, row: CommentOrm) -> CommentSummary:
        post_public_id = self._session.scalar(
            select(PostOrm.public_id).where(PostOrm.id == row.post_id)
        )
        if post_public_id is None:
            # Back-fill defensively — listing should not crash if the post is
            # missing its public_id for some reason.
            from uuid import uuid4

            post_public_id = uuid4()

        parent_public_id: UUID | None = None
        if row.parent_id is not None:
            parent_public_id = self._session.scalar(
                select(CommentOrm.public_id).where(CommentOrm.id == row.parent_id)
            )

        if row.author_id is not None:
            author_row = self._session.execute(
                select(UserOrm.public_id, UserOrm.username).where(UserOrm.id == row.author_id)
            ).one_or_none()
            if author_row is None:
                author = AuthorSummary(public_id=None, username=None)
            else:
                author = AuthorSummary(public_id=author_row[0], username=author_row[1])
        else:
            author = AuthorSummary(public_id=None, username=None)

        return comment_summary_from_row(
            row,
            post_public_id=post_public_id,
            parent_public_id=parent_public_id,
            author=author,
        )


# Time helper not used here directly — re-exported for callers that build
# domain instances manually in tests.
def _now() -> datetime:
    return datetime.now(UTC)
