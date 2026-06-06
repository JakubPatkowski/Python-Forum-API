"""Tag entity — a free-form label attached to posts (M:N)."""

from __future__ import annotations

from app.modules.content.domain.value_objects import Slug
from app.shared.domain.entity import Entity
from app.shared.domain.entity_id import EntityId


class TagId(EntityId["Tag"]):
    """Public identifier (UUID) of a :class:`Tag`."""


class Tag(Entity[TagId]):
    """A short, lowercase label attached to one or more posts.

    Names are case-insensitive at the database level — we store the
    canonical lowercase form and a matching slug.
    """

    def __init__(self, *, id: TagId, name: str, slug: Slug) -> None:
        self.id = id
        self._name = name
        self._slug = slug

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> Slug:
        return self._slug

    @classmethod
    def create(cls, name: str) -> Tag:
        """Build a Tag from raw text, deriving a slug automatically."""
        cleaned = name.strip().lower()
        if not cleaned:
            from app.shared.domain.errors import ValidationError

            raise ValidationError("Tag name must not be empty", field="name")
        if len(cleaned) > 50:
            from app.shared.domain.errors import ValidationError

            raise ValidationError(
                "Tag name must be at most 50 characters", field="name"
            )
        return cls(
            id=TagId.new(),
            name=cleaned,
            slug=Slug.from_text(cleaned, max_length=60),
        )
