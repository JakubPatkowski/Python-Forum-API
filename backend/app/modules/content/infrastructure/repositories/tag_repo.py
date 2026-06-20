"""SqlAlchemy implementation of :class:`ITagRepository`."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.content.application.ports import ITagRepository
from app.modules.content.domain.tag import Tag, TagId
from app.modules.content.domain.value_objects import Slug
from app.modules.content.infrastructure.mappers import tag_from_orm
from app.modules.content.infrastructure.orm import TagOrm


class SqlAlchemyTagRepository(ITagRepository):
    """Persistence layer for tags. Tags are write-light, read-heavy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id_: TagId) -> Tag | None:
        row = self._session.scalar(select(TagOrm).where(TagOrm.public_id == id_.value))
        return tag_from_orm(row) if row else None

    async def get_by_name(self, name: str) -> Tag | None:
        row = self._session.scalar(select(TagOrm).where(TagOrm.name == name.strip().lower()))
        return tag_from_orm(row) if row else None

    async def get_by_slug(self, slug: str) -> Tag | None:
        row = self._session.scalar(select(TagOrm).where(TagOrm.slug == slug))
        return tag_from_orm(row) if row else None

    async def add(self, tag: Tag) -> None:
        row = TagOrm(
            public_id=tag.id.value,
            name=tag.name,
            slug=str(tag.slug),
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()

    async def upsert_many_by_name(self, names: list[str]) -> list[Tag]:
        """Return a Tag for every name, creating missing ones in bulk.

        Order of returned tags matches the order of distinct cleaned names.
        """
        cleaned = [n.strip().lower() for n in names if n.strip()]
        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique_names: list[str] = []
        for n in cleaned:
            if n not in seen:
                seen.add(n)
                unique_names.append(n)
        if not unique_names:
            return []

        existing_rows = self._session.scalars(
            select(TagOrm).where(TagOrm.name.in_(unique_names))
        ).all()
        existing_by_name = {row.name: row for row in existing_rows}

        for name in unique_names:
            if name in existing_by_name:
                continue
            tag = Tag.create(name)
            row = TagOrm(
                public_id=tag.id.value,
                name=tag.name,
                slug=str(tag.slug),
                created_at=datetime.now(UTC),
            )
            self._session.add(row)
            existing_by_name[name] = row

        # Flush so any newly inserted tags have their integer ids if the
        # caller needs them for the post_tags link table.
        self._session.flush()
        return [tag_from_orm(existing_by_name[n]) for n in unique_names]

    async def list_all(self) -> list[Tag]:
        rows = self._session.scalars(select(TagOrm).order_by(TagOrm.name)).all()
        return [tag_from_orm(r) for r in rows]


def slug_from_text(text: str) -> Slug:
    """Module-local helper kept here so other tag-related code can reuse it."""
    return Slug.from_text(text, max_length=60)
