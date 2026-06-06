"""User aggregate root.

The User owns its set of roles and direct permission overrides. All
mutations go through aggregate methods so domain events are recorded
consistently. Persistence is the infrastructure layer's concern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from app.modules.identity.domain.events import (
    UserBlocked,
    UserPermissionChanged,
    UserRegistered,
    UserRoleChanged,
    UserUnblocked,
)
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.role import Role
from app.modules.identity.domain.value_objects import Email, Username
from app.shared.domain.entity import AggregateRoot
from app.shared.domain.entity_id import EntityId
from app.shared.domain.errors import ValidationError


class UserId(EntityId["User"]):
    """Public identifier (UUID) of a User."""


class UserStatus(StrEnum):
    """Lifecycle status of a User account."""

    ACTIVE = "active"
    BLOCKED = "blocked"
    PENDING_VERIFICATION = "pending_verification"


class User(AggregateRoot[UserId]):
    """Aggregate root for an authenticated user identity.

    Holds:
    - identifying fields (``username``, ``email``),
    - the Argon2-encoded ``password_hash`` (never the plaintext),
    - lifecycle ``status``,
    - roles and per-user permission overrides.
    """

    def __init__(
        self,
        *,
        id: UserId,
        username: Username,
        email: Email,
        password_hash: str,
        status: UserStatus = UserStatus.ACTIVE,
        roles: set[Role] | None = None,
        granted_permissions: set[Permission] | None = None,
        denied_permissions: set[Permission] | None = None,
        avatar_file_id: int | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self._username = username
        self._email = email
        self._password_hash = password_hash
        self._status = status
        self._roles: set[Role] = set(roles or ())
        self._granted: set[Permission] = set(granted_permissions or ())
        self._denied: set[Permission] = set(denied_permissions or ())
        self.avatar_file_id = avatar_file_id
        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    # --- read-only accessors ------------------------------------------------

    @property
    def username(self) -> Username:
        return self._username

    @property
    def email(self) -> Email:
        return self._email

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def status(self) -> UserStatus:
        return self._status

    @property
    def is_active(self) -> bool:
        return self._status == UserStatus.ACTIVE

    @property
    def roles(self) -> frozenset[Role]:
        return frozenset(self._roles)

    @property
    def granted_permissions(self) -> frozenset[Permission]:
        return frozenset(self._granted)

    @property
    def denied_permissions(self) -> frozenset[Permission]:
        return frozenset(self._denied)

    def effective_permissions(self) -> frozenset[Permission]:
        """Compute the effective permission set per RBAC + ACL rules.

        Algorithm (mirrors ``v_user_effective_permissions``):
            (∪ permissions of roles) ∪ direct_grants  \\  direct_denies
        """
        combined: set[Permission] = set()
        for role in self._roles:
            combined.update(role.permissions)
        combined.update(self._granted)
        combined.difference_update(self._denied)
        return frozenset(combined)

    def has_permission(self, code: str) -> bool:
        return Permission(code) in self.effective_permissions()

    # --- factories ----------------------------------------------------------

    @classmethod
    def register(
        cls,
        *,
        username: Username,
        email: Email,
        password_hash: str,
        default_role: Role,
    ) -> User:
        """Factory for fresh registrations. Emits :class:`UserRegistered`."""
        user = cls(
            id=UserId.new(),
            username=username,
            email=email,
            password_hash=password_hash,
            status=UserStatus.ACTIVE,
            roles={default_role},
        )
        user.record_event(
            UserRegistered(
                user_id=user.id.value,
                username=str(username),
                email=str(email),
            )
        )
        return user

    # --- mutations ----------------------------------------------------------

    def change_password(self, new_password_hash: str) -> None:
        if not new_password_hash:
            raise ValidationError("Password hash must be non-empty", field="password")
        self._password_hash = new_password_hash
        self._touch()

    def block(self, *, by: UserId | None = None) -> None:
        if self._status == UserStatus.BLOCKED:
            return
        self._status = UserStatus.BLOCKED
        self._touch()
        self.record_event(
            UserBlocked(user_id=self.id.value, blocked_by=by.value if by else None)
        )

    def unblock(self, *, by: UserId | None = None) -> None:
        if self._status == UserStatus.ACTIVE:
            return
        self._status = UserStatus.ACTIVE
        self._touch()
        self.record_event(
            UserUnblocked(
                user_id=self.id.value, unblocked_by=by.value if by else None
            )
        )

    def assign_role(self, role: Role, *, by: UserId | None = None) -> None:
        if role in self._roles:
            return
        self._roles.add(role)
        self._touch()
        self.record_event(
            UserRoleChanged(
                user_id=self.id.value,
                role_name=role.name,
                granted=True,
                changed_by=by.value if by else None,
            )
        )

    def revoke_role(self, role: Role, *, by: UserId | None = None) -> None:
        if role not in self._roles:
            return
        self._roles.discard(role)
        self._touch()
        self.record_event(
            UserRoleChanged(
                user_id=self.id.value,
                role_name=role.name,
                granted=False,
                changed_by=by.value if by else None,
            )
        )

    def grant_permission(
        self, permission: Permission, *, by: UserId | None = None
    ) -> None:
        """Add a per-user permission override that grants the code."""
        self._denied.discard(permission)
        if permission in self._granted:
            return
        self._granted.add(permission)
        self._touch()
        self.record_event(
            UserPermissionChanged(
                user_id=self.id.value,
                permission_code=permission.code,
                granted=True,
                changed_by=by.value if by else None,
            )
        )

    def deny_permission(
        self, permission: Permission, *, by: UserId | None = None
    ) -> None:
        """Add a per-user permission override that denies the code."""
        self._granted.discard(permission)
        if permission in self._denied:
            return
        self._denied.add(permission)
        self._touch()
        self.record_event(
            UserPermissionChanged(
                user_id=self.id.value,
                permission_code=permission.code,
                granted=False,
                changed_by=by.value if by else None,
            )
        )

    def clear_permission_override(
        self, permission: Permission, *, by: UserId | None = None
    ) -> None:
        """Remove any per-user override for the given permission.

        Resulting access is whatever the user's roles grant.
        """
        was_granted = permission in self._granted
        was_denied = permission in self._denied
        if not was_granted and not was_denied:
            return
        self._granted.discard(permission)
        self._denied.discard(permission)
        self._touch()
        self.record_event(
            UserPermissionChanged(
                user_id=self.id.value,
                permission_code=permission.code,
                granted=False,
                changed_by=by.value if by else None,
            )
        )

    def set_avatar(self, file_id: int | None) -> None:
        self.avatar_file_id = file_id
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
