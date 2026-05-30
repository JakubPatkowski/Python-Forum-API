"""SqlAlchemy implementation of :class:`IPostRepository`.

Posts are joined with categories, tags and the author username so the
``PostSummary`` projection can be built in a single set of queries
without further round-trips. The repository keeps it simple: a couple
of small queries rather than one giant join, because Phase 6 will move
the listing onto the dedicated ``v_posts_with_stats`` view.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.post import ContentFormat as LegacyContentFormat
from app.models.user import User as UserOrm
from app.modules.content.application.commands import (
    AuthorSummary,
    CategorySummary,
    PostListPage,
    PostSummary,
    TagSummary,
)
from app.modules.content.application.pagination import PostCursor
from app.modules.content.application.ports import IPostRepository
from app.modules.content.domain.post import Post, PostId
from app.modules.content.domain.tag import Tag
from app.modules.content.infrastructure.mappers import (
    category_summary_from_orm,
    post_from_orm,
    post_summary_from_row,
    tag_from_orm,
    tag_summary_from_orm,
)
from app.modules.content.infrastructure.orm import (
    CategoryOrm,
    CommentOrm,
    PostOrm,
    PostTagOrm,
    TagOrm,
)


UserIdResolver = Callable[[UUID], int | None]


class SqlAlchemyPostRepository(IPostRepository):
    """Persistence port for :class:`Post` aggregates."""

    def __init__(
        self,
        session: Session,
        *,
        user_id_resolver: UserIdResolver,
    ) -> None:
        self._session = session
        self._resolve_user_id = user_id_resolver

    # --- read --------------------------------------------------------------

    async def get(self, id_: PostId) -> Post | None:
        row = self._session.scalar(
            select(PostOrm).where(PostOrm.public_id == id_.value)
        )
        if row is None:
            return None
        return self._hydrate_post(row)

    async def exists(self, id_: PostId) -> bool:
        return (
            self._session.scalar(
                select(PostOrm.id).where(PostOrm.public_id == id_.value)
            )
            is not None
        )

    async def get_with_summary(self, id_: PostId) -> PostSummary | None:
        row = self._session.scalar(
            select(PostOrm).where(PostOrm.public_id == id_.value)
        )
        if row is None:
            return None
        return self._project_summary(row)

    async def has_slug_for_author(
        self,
        *,
        author_public_id: UUID,
        slug: str,
        exclude_id: PostId | None = None,
    ) -> bool:
        user_id = self._resolve_user_id(author_public_id)
        if user_id is None:
            return False
        stmt = select(PostOrm.id).where(
            PostOrm.author_id == user_id,
            PostOrm.slug == slug,
        )
        if exclude_id is not None:
            stmt = stmt.where(PostOrm.public_id != exclude_id.value)
        return self._session.scalar(stmt) is not None

    async def list_summaries(
        self,
        *,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
        category_public_id: UUID | None = None,
        tag_slug: str | None = None,
        author_public_id: UUID | None = None,
    ) -> PostListPage:
        stmt = select(PostOrm).where(PostOrm.is_deleted.is_(False))
        if category_public_id is not None:
            stmt = stmt.join(
                CategoryOrm, CategoryOrm.id == PostOrm.category_id
            ).where(CategoryOrm.public_id == category_public_id)
        if tag_slug is not None:
            stmt = (
                stmt.join(PostTagOrm, PostTagOrm.post_id == PostOrm.id)
                .join(TagOrm, TagOrm.id == PostTagOrm.tag_id)
                .where(TagOrm.slug == tag_slug)
            )
        if author_public_id is not None:
            stmt = stmt.join(UserOrm, UserOrm.id == PostOrm.author_id).where(
                UserOrm.public_id == author_public_id
            )

        # Keyset predicate: strictly older than the cursor row.
        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    PostOrm.created_at < cursor_created_at,
                    and_(
                        PostOrm.created_at == cursor_created_at,
                        PostOrm.public_id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(
            PostOrm.created_at.desc(), PostOrm.public_id.desc()
        ).limit(limit + 1)

        rows = self._session.scalars(stmt).all()

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]

        summaries = tuple(self._project_summary(row) for row in rows)
        if len(summaries) == limit:
            tail = summaries[-1]
            next_cursor = PostCursor(
                created_at=tail.created_at, public_id=tail.public_id
            ).encode()
        return PostListPage(items=summaries, next_cursor=next_cursor)

    # --- write -------------------------------------------------------------

    async def add(self, entity: Post) -> None:
        """Insert or update the post and synchronise its tag links."""
        author_db_id = self._resolve_user_id(entity.author_id.value)
        if author_db_id is None:
            raise ValueError(
                f"Unknown author {entity.author_id.value} — user must exist first"
            )
        category_db_id = self._resolve_category_id(entity.category_id.value) if entity.category_id else None
        if entity.category_id and category_db_id is None:
            raise ValueError(
                f"Unknown category {entity.category_id.value} — must exist first"
            )

        row = self._session.scalar(
            select(PostOrm).where(PostOrm.public_id == entity.id.value)
        )
        if row is None:
            row = PostOrm(
                public_id=entity.id.value,
                title=entity.title,
                content=entity.content.body,
                content_format=LegacyContentFormat(entity.content.format.value),
                author_id=author_db_id,
                category_id=category_db_id,
                slug=str(entity.slug),
                is_deleted=entity.is_deleted,
                created_at=entity.created_at.replace(tzinfo=None),
                updated_at=entity.updated_at.replace(tzinfo=None),
            )
            self._session.add(row)
            self._session.flush()
        else:
            row.title = entity.title
            row.content = entity.content.body
            row.content_format = LegacyContentFormat(entity.content.format.value)
            row.category_id = category_db_id
            row.slug = str(entity.slug)
            row.is_deleted = entity.is_deleted
            row.updated_at = entity.updated_at.replace(tzinfo=None)

        self._sync_tags(row.id, entity.tags)

    async def remove(self, entity: Post) -> None:
        self._session.execute(
            PostOrm.__table__.delete().where(
                PostOrm.public_id == entity.id.value
            )
        )

    # --- helpers ------------------------------------------------------------

    def _resolve_category_id(self, public_id: UUID) -> int | None:
        return self._session.scalar(
            select(CategoryOrm.id).where(CategoryOrm.public_id == public_id)
        )

    def _hydrate_post(self, row: PostOrm) -> Post:
        category = None
        if row.category_id is not None:
            cat_row = self._session.scalar(
                select(CategoryOrm).where(CategoryOrm.id == row.category_id)
            )
            if cat_row is not None and cat_row.public_id is not None:
                from app.modules.content.infrastructure.mappers import (
                    category_from_orm,
                )

                category = category_from_orm(cat_row)

        tag_rows = self._session.scalars(
            select(TagOrm).join(PostTagOrm, PostTagOrm.tag_id == TagOrm.id).where(
                PostTagOrm.post_id == row.id
            )
        ).all()
        tags: set[Tag] = {tag_from_orm(t) for t in tag_rows}

        author_public_id = self._session.scalar(
            select(UserOrm.public_id).where(UserOrm.id == row.author_id)
        )
        # Older legacy users may not have a public_id yet; back-fill defensively.
        if author_public_id is None:
            from uuid import uuid4 as _uuid4

            author_public_id = _uuid4()
            self._session.execute(
                UserOrm.__table__.update()
                .where(UserOrm.id == row.author_id)
                .values(public_id=author_public_id)
            )

        return post_from_orm(
            row,
            category=category,
            tags=tags,
            author_public_id=author_public_id,
        )

    def _project_summary(self, row: PostOrm) -> PostSummary:
        # Author summary
        author_row = self._session.execute(
            select(UserOrm.public_id, UserOrm.username).where(
                UserOrm.id == row.author_id
            )
        ).one_or_none()
        if author_row is None:
            author = AuthorSummary(public_id=None, username=None)
        else:
            author = AuthorSummary(
                public_id=author_row[0], username=author_row[1]
            )

        # Category summary
        category_summary: CategorySummary | None = None
        if row.category_id is not None:
            cat_row = self._session.scalar(
                select(CategoryOrm).where(CategoryOrm.id == row.category_id)
            )
            if cat_row is not None and cat_row.public_id is not None and cat_row.slug is not None:
                category_summary = category_summary_from_orm(cat_row)

        # Tag summaries
        tag_rows = self._session.scalars(
            select(TagOrm)
            .join(PostTagOrm, PostTagOrm.tag_id == TagOrm.id)
            .where(PostTagOrm.post_id == row.id)
            .order_by(TagOrm.name)
        ).all()
        tags: tuple[TagSummary, ...] = tuple(
            tag_summary_from_orm(t) for t in tag_rows
        )

        # Comment count — count both legacy and phase-2 comments. ``is_deleted``
        # may be NULL on legacy rows from before migration 0004; treat as live.
        comment_count = (
            self._session.scalar(
                select(func.count(CommentOrm.id)).where(
                    CommentOrm.post_id == row.id,
                    or_(
                        CommentOrm.is_deleted.is_(False),
                        CommentOrm.is_deleted.is_(None),
                    ),
                )
            )
            or 0
        )

        return post_summary_from_row(
            row,
            author=author,
            category=category_summary,
            tags=tags,
            comment_count=int(comment_count),
        )

    def _sync_tags(self, post_db_id: int, tags) -> None:
        """Diff existing ``post_tags`` rows against the desired tag set."""
        desired_public_ids = {t.id.value for t in tags}

        if not desired_public_ids:
            self._session.execute(
                PostTagOrm.__table__.delete().where(
                    PostTagOrm.post_id == post_db_id
                )
            )
            return

        tag_db_rows = self._session.execute(
            select(TagOrm.id, TagOrm.public_id).where(
                TagOrm.public_id.in_(desired_public_ids)
            )
        ).all()
        desired_db_ids = {r[0] for r in tag_db_rows}

        existing_db_ids = {
            r
            for r in self._session.scalars(
                select(PostTagOrm.tag_id).where(
                    PostTagOrm.post_id == post_db_id
                )
            ).all()
        }
        # Delete removed links
        to_remove = existing_db_ids - desired_db_ids
        if to_remove:
            self._session.execute(
                PostTagOrm.__table__.delete().where(
                    PostTagOrm.post_id == post_db_id,
                    PostTagOrm.tag_id.in_(to_remove),
                )
            )
        # Insert new links
        for tag_db_id in desired_db_ids - existing_db_ids:
            self._session.add(
                PostTagOrm(post_id=post_db_id, tag_id=tag_db_id)
            )
