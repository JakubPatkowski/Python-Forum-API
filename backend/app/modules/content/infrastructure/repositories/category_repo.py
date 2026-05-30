"""SqlAlchemy implementation of :class:`ICategoryRepository`."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.content.application.commands import CategorySummary
from app.modules.content.application.ports import ICategoryRepository
from app.modules.content.domain.category import Category, CategoryId
from app.modules.content.infrastructure.mappers import (
    category_from_orm,
    category_summary_from_orm,
)
from app.modules.content.infrastructure.orm import CategoryOrm


class SqlAlchemyCategoryRepository(ICategoryRepository):
    """Persistence layer for categories."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id_: CategoryId) -> Category | None:
        row = self._session.scalar(
            select(CategoryOrm).where(CategoryOrm.public_id == id_.value)
        )
        return category_from_orm(row) if row else None

    async def get_by_name(self, name: str) -> Category | None:
        row = self._session.scalar(
            select(CategoryOrm).where(CategoryOrm.name == name.strip())
        )
        return category_from_orm(row) if row else None

    async def get_by_slug(self, slug: str) -> Category | None:
        row = self._session.scalar(
            select(CategoryOrm).where(CategoryOrm.slug == slug)
        )
        return category_from_orm(row) if row else None

    async def add(self, entity: Category) -> None:
        row = self._session.scalar(
            select(CategoryOrm).where(CategoryOrm.public_id == entity.id.value)
        )
        if row is None:
            row = CategoryOrm(
                public_id=entity.id.value,
                name=entity.name,
                slug=str(entity.slug),
                description=entity.description,
                created_at=entity.created_at or datetime.now(UTC),
            )
            self._session.add(row)
        else:
            row.name = entity.name
            row.slug = str(entity.slug)
            row.description = entity.description
        self._session.flush()

    async def remove(self, entity: Category) -> None:
        self._session.execute(
            CategoryOrm.__table__.delete().where(
                CategoryOrm.public_id == entity.id.value
            )
        )

    async def exists(self, id_: CategoryId) -> bool:
        return (
            self._session.scalar(
                select(CategoryOrm.id).where(CategoryOrm.public_id == id_.value)
            )
            is not None
        )

    async def list_all(self) -> list[CategorySummary]:
        rows = self._session.scalars(
            select(CategoryOrm).order_by(CategoryOrm.name)
        ).all()
        return [category_summary_from_orm(r) for r in rows]
