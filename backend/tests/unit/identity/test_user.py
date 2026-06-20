"""Unit tests for the :class:`User` aggregate.

These exercise the domain in isolation — no DB, no FastAPI, no JWT.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.modules.identity.domain.events import (
    UserBlocked,
    UserPermissionChanged,
    UserRegistered,
    UserRoleChanged,
)
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.domain.user import User, UserStatus
from app.modules.identity.domain.value_objects import Email, Username


def _make_role(name: str, codes: list[str]) -> Role:
    return Role(
        id=RoleId(UUID(int=hash(name) & ((1 << 128) - 1))),
        name=name,
        permissions={Permission(c) for c in codes},
    )


@pytest.fixture
def user_role() -> Role:
    return _make_role("user", ["post.create", "comment.create"])


@pytest.fixture
def mod_role() -> Role:
    return _make_role(
        "moderator",
        ["post.create", "comment.create", "post.delete.any", "comment.delete.any"],
    )


class TestRegister:
    def test_records_user_registered_event(self, user_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="$argon2id$...",
            default_role=user_role,
        )
        events = user.pull_events()
        assert any(isinstance(e, UserRegistered) for e in events)
        assert user.status == UserStatus.ACTIVE
        assert user.is_active
        assert {r.name for r in user.roles} == {"user"}


class TestBlocking:
    def test_block_marks_inactive_and_records_event(self, user_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=user_role,
        )
        user.pull_events()
        user.block()
        assert user.status == UserStatus.BLOCKED
        events = user.pull_events()
        assert any(isinstance(e, UserBlocked) for e in events)

    def test_blocking_twice_is_idempotent(self, user_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=user_role,
        )
        user.pull_events()
        user.block()
        first_events = user.pull_events()
        user.block()
        assert user.pull_events() == []
        assert any(isinstance(e, UserBlocked) for e in first_events)


class TestRoles:
    def test_assign_role_records_event(self, user_role: Role, mod_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=user_role,
        )
        user.pull_events()
        user.assign_role(mod_role)
        events = user.pull_events()
        role_events = [e for e in events if isinstance(e, UserRoleChanged)]
        assert role_events and role_events[0].granted is True
        assert role_events[0].role_name == "moderator"

    def test_effective_permissions_union_of_roles(self, user_role: Role, mod_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=user_role,
        )
        user.assign_role(mod_role)
        codes = {p.code for p in user.effective_permissions()}
        assert "post.delete.any" in codes
        assert "post.create" in codes


class TestPermissionOverrides:
    def test_deny_overrides_role_grant(self, mod_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=mod_role,
        )
        user.pull_events()
        user.deny_permission(Permission("post.delete.any"))
        events = user.pull_events()
        assert any(isinstance(e, UserPermissionChanged) and e.granted is False for e in events)
        assert not user.has_permission("post.delete.any")

    def test_grant_adds_permission_not_in_role(self, user_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=user_role,
        )
        assert not user.has_permission("audit.read")
        user.grant_permission(Permission("audit.read"))
        assert user.has_permission("audit.read")

    def test_clear_override_revokes_both_directions(self, user_role: Role) -> None:
        user = User.register(
            username=Username("jakub"),
            email=Email("jakub@example.com"),
            password_hash="hash",
            default_role=user_role,
        )
        user.grant_permission(Permission("audit.read"))
        user.clear_permission_override(Permission("audit.read"))
        assert not user.has_permission("audit.read")
        assert Permission("audit.read") not in user.granted_permissions
        assert Permission("audit.read") not in user.denied_permissions
