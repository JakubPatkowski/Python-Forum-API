"""Smoke tests for :class:`PyJWTTokenService` — issue + decode round-trip."""

from __future__ import annotations

from uuid import uuid4

from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.domain.user import User, UserId, UserStatus
from app.modules.identity.domain.value_objects import Email, Username
from app.modules.identity.infrastructure.auth import PyJWTTokenService


def _user() -> User:
    role = Role(
        id=RoleId(uuid4()),
        name="user",
        permissions={Permission("post.read"), Permission("post.create")},
    )
    return User(
        id=UserId(uuid4()),
        username=Username("jakub"),
        email=Email("jakub@example.com"),
        password_hash="$argon2id$...",
        status=UserStatus.ACTIVE,
        roles={role},
    )


def test_access_token_round_trip() -> None:
    svc = PyJWTTokenService(secret_key="testsecret", algorithm="HS256")
    user = _user()
    issued = svc.issue_access(user)
    claims = svc.decode_access(issued.jwt)
    assert claims is not None
    assert claims.user_public_id == user.id.value
    assert claims.username == str(user.username)
    assert set(claims.permissions) == {"post.read", "post.create"}


def test_refresh_token_round_trip() -> None:
    svc = PyJWTTokenService(secret_key="testsecret", algorithm="HS256")
    user = _user()
    issued = svc.issue_refresh(user, user_agent="UA", ip_address="127.0.0.1")
    claims = svc.decode_refresh(issued.jwt)
    assert claims is not None
    assert claims.user_public_id == user.id.value
    assert claims.token_public_id == issued.record.id.value


def test_access_token_rejected_as_refresh() -> None:
    svc = PyJWTTokenService(secret_key="testsecret", algorithm="HS256")
    issued = svc.issue_access(_user())
    assert svc.decode_refresh(issued.jwt) is None


def test_tampered_token_decodes_to_none() -> None:
    svc = PyJWTTokenService(secret_key="testsecret", algorithm="HS256")
    issued = svc.issue_access(_user())
    assert svc.decode_access(issued.jwt + "tampered") is None


def test_token_hash_is_stable() -> None:
    svc = PyJWTTokenService()
    a = svc.hash_token("hello")
    b = svc.hash_token("hello")
    assert a == b
    assert len(a) == 64  # sha256 hex
