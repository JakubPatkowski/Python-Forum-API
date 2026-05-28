"""Category entity — a coarse topical bucket assigned to posts."""

from __future__ import annotations

from datetime import UTC, datetime

from app.shared.domain.entity import Entity
from app.shared.domain.entity_id import EntityId

from app.modules.content.domain.value_objects import Slug


class CategoryId(EntityId["Category"]):
    """Public identifier (UUID) of a :class:`Category`."""


class Category(Entity[CategoryId]):
    """A named bucket for posts. Categories are seeded by the admin.

    Examples: ``Spinning``, ``Karpiowanie``, ``Muszka``.
    """

    def __init__(
        self,
        *,
        id: CategoryId,
        name: str,
        slug: Slug,
        description: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self._name = name
        self._slug = slug
        self.description = description
        self.created_at = created_at or datetime.now(UTC)

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> Slug:
        return self._slug

    def rename(self, name: str, *, slug: Slug | None = None) -> None:
        if not name.strip():
            from app.shared.domain.errors import ValidationError

            raise ValidationError("Category name must not be empty", field="name")
        self._name = name.strip()
        if slug is not None:
            self._slug = slug
