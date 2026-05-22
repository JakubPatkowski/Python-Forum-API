"""Role entity — a named bundle of permissions."""

from __future__ import annotations

from app.shared.domain.entity import Entity
from app.shared.domain.entity_id import EntityId

from app.modules.identity.domain.permission import Permission


class RoleId(EntityId["Role"]):
    """Public identifier of a Role."""


class Role(Entity[RoleId]):
    """A reusable bundle of permissions identified by a stable name.

    Roles are sparingly modified; most permission tuning happens through the
    ``Permission`` overrides on ``User`` itself. Predefined roles ``user``,
    ``moderator``, ``admin`` are seeded by migration 0003.
    """

    def __init__(
        self,
        *,
        id: RoleId,
        name: str,
        permissions: set[Permission],
        description: str | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self._permissions: set[Permission] = set(permissions)

    @property
    def permissions(self) -> frozenset[Permission]:
        """Return an immutable snapshot of role permissions."""
        return frozenset(self._permissions)

    def grant(self, permission: Permission) -> None:
        self._permissions.add(permission)

    def revoke(self, permission: Permission) -> None:
        self._permissions.discard(permission)
