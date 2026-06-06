"""Post aggregate root.

The Post owns the body, the category link and the set of tags assigned to
it. Comments are a *separate* aggregate (kept small to avoid loading the
whole thread on every post mutation).

Soft delete is preferred over hard delete so links from notifications,
audit logs and search indexes stay intact.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.content.domain.category import CategoryId
from app.modules.content.domain.events import (
    PostCreated,
    PostDeleted,
    PostUpdated,
)
from app.modules.content.domain.tag import Tag
from app.modules.content.domain.value_objects import (
    ContentFormat,
    MarkdownContent,
    Slug,
)

# UserId from identity is referenced by UUID only — content doesn't import
# the User aggregate to keep modules independent.
from app.modules.identity.domain.user import UserId
from app.shared.domain.entity import AggregateRoot
from app.shared.domain.entity_id import EntityId
from app.shared.domain.errors import ValidationError


class PostId(EntityId["Post"]):
    """Public identifier (UUID) of a :class:`Post`."""


class Post(AggregateRoot[PostId]):
    """A forum thread starter — title, body, optional category and tags."""

    _TITLE_MIN: int = 3
    _TITLE_MAX: int = 200

    def __init__(
        self,
        *,
        id: PostId,
        author_id: UserId,
        title: str,
        slug: Slug,
        content: MarkdownContent,
        category_id: CategoryId | None = None,
        tags: set[Tag] | None = None,
        is_deleted: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self._author_id = author_id
        self._title = title
        self._slug = slug
        self._content = content
        self._category_id = category_id
        self._tags: set[Tag] = set(tags or ())
        self._is_deleted = is_deleted
        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    # --- read-only accessors -----------------------------------------------

    @property
    def author_id(self) -> UserId:
        return self._author_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def slug(self) -> Slug:
        return self._slug

    @property
    def content(self) -> MarkdownContent:
        return self._content

    @property
    def category_id(self) -> CategoryId | None:
        return self._category_id

    @property
    def tags(self) -> frozenset[Tag]:
        return frozenset(self._tags)

    @property
    def is_deleted(self) -> bool:
        return self._is_deleted

    # --- factories ----------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        author_id: UserId,
        title: str,
        content: MarkdownContent,
        category_id: CategoryId | None = None,
        tags: set[Tag] | None = None,
        slug: Slug | None = None,
    ) -> Post:
        """Factory for fresh posts. Emits :class:`PostCreated`."""
        cls._validate_title(title)
        derived_slug = slug or Slug.from_text(title)
        post = cls(
            id=PostId.new(),
            author_id=author_id,
            title=title.strip(),
            slug=derived_slug,
            content=content,
            category_id=category_id,
            tags=tags,
        )
        post.record_event(
            PostCreated(
                post_id=post.id.value,
                author_id=author_id.value,
                title=post.title,
                slug=str(derived_slug),
                category_id=category_id.value if category_id else None,
            )
        )
        return post

    # --- mutations ----------------------------------------------------------

    def edit(
        self,
        *,
        title: str | None = None,
        content: MarkdownContent | None = None,
        category_id: CategoryId | None = None,
        tags: set[Tag] | None = None,
        slug: Slug | None = None,
        updated_by: UserId | None = None,
    ) -> None:
        """Update one or more fields. Pass only what changes."""
        if self._is_deleted:
            raise ValidationError("Cannot edit a deleted post", field="post")
        changed = False
        if title is not None and title != self._title:
            self._validate_title(title)
            self._title = title.strip()
            changed = True
        if content is not None and content != self._content:
            self._content = content
            changed = True
        if category_id is not None and category_id != self._category_id:
            self._category_id = category_id
            changed = True
        if tags is not None and set(tags) != self._tags:
            self._tags = set(tags)
            changed = True
        if slug is not None and slug != self._slug:
            self._slug = slug
            changed = True
        if changed:
            self._touch()
            self.record_event(
                PostUpdated(
                    post_id=self.id.value,
                    author_id=self._author_id.value,
                    updated_by=updated_by.value if updated_by else None,
                )
            )

    def soft_delete(self, *, deleted_by: UserId | None = None) -> None:
        if self._is_deleted:
            return
        self._is_deleted = True
        self._touch()
        self.record_event(
            PostDeleted(
                post_id=self.id.value,
                author_id=self._author_id.value,
                deleted_by=deleted_by.value if deleted_by else None,
            )
        )

    def set_format(self, fmt: ContentFormat) -> None:
        if fmt == self._content.format:
            return
        self._content = MarkdownContent(body=self._content.body, format=fmt)
        self._touch()

    # --- helpers ------------------------------------------------------------

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    @classmethod
    def _validate_title(cls, title: str) -> None:
        v = title.strip()
        if len(v) < cls._TITLE_MIN:
            raise ValidationError(
                f"Title must be at least {cls._TITLE_MIN} characters", field="title"
            )
        if len(v) > cls._TITLE_MAX:
            raise ValidationError(
                f"Title must be at most {cls._TITLE_MAX} characters", field="title"
            )
