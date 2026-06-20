"""Permission Value Object and the canonical permission code catalogue.

Permissions follow the convention ``<resource>.<action>[.<scope>]`` where
``.own`` means "only the resource owner" and ``.any`` means "any resource".
The catalogue is part of the domain because it is a business concept (what
a user is allowed to do), not an infrastructure detail.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class Permission(ValueObject):
    """A single permission code, e.g. ``post.delete.any``."""

    code: str

    def __post_init__(self) -> None:
        if not self.code or any(ch.isspace() for ch in self.code):
            raise ValidationError(f"Invalid permission code: {self.code!r}")

    def __str__(self) -> str:
        return self.code


# --------------------------------------------------------------------------- #
# Permission catalogue
# --------------------------------------------------------------------------- #
# Mirrors docs/02-database-schema.md §2 and docs/03-security.md §3.2.
# Add codes here, then make sure the seed migration inserts them.

PERMISSION_CODES: tuple[str, ...] = (
    # posts
    "post.read",
    "post.create",
    "post.update.own",
    "post.update.any",
    "post.delete.own",
    "post.delete.any",
    # comments
    "comment.read",
    "comment.create",
    "comment.update.own",
    "comment.update.any",
    "comment.delete.own",
    "comment.delete.any",
    # files
    "file.upload",
    "file.download",
    "file.delete.own",
    "file.delete.any",
    # categories / tags
    "category.create",
    "category.manage",
    "tag.manage",
    # admin
    "user.read.any",
    "user.manage",
    "role.manage",
    "audit.read",
)

# Predefined role bundles. Custom roles can be created later through the API.
_USER_BUNDLE: tuple[str, ...] = (
    "post.read",
    "post.create",
    "post.update.own",
    "post.delete.own",
    "comment.read",
    "comment.create",
    "comment.update.own",
    "comment.delete.own",
    "file.upload",
    "file.download",
    "file.delete.own",
    # Any logged-in user can create a new category (product decision).
    # Deleting a category stays with the moderator (``category.manage``).
    "category.create",
)

_MOD_EXTRA: tuple[str, ...] = (
    "post.update.any",
    "post.delete.any",
    "comment.update.any",
    "comment.delete.any",
    "file.delete.any",
    "category.manage",
    "tag.manage",
)

_ADMIN_EXTRA: tuple[str, ...] = (
    "user.read.any",
    "user.manage",
    "role.manage",
    "audit.read",
)

ROLE_BUNDLES: dict[str, tuple[str, ...]] = {
    "user": _USER_BUNDLE,
    "moderator": _USER_BUNDLE + _MOD_EXTRA,
    "admin": _USER_BUNDLE + _MOD_EXTRA + _ADMIN_EXTRA,
}
