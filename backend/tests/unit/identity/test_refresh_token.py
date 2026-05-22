"""Unit tests for the :class:`RefreshToken` entity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.identity.domain.refresh_token import (
    RefreshToken,
    RefreshTokenId,
    TokenStatus,
)
from app.modules.identity.domain.user import UserId


def _make_token() -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId(uuid4()),
        user_id=UserId(uuid4()),
        token_hash="0" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=14),
    )


def test_fresh_token_is_active() -> None:
    t = _make_token()
    assert t.is_active is True
    assert t.is_rotated is False


def test_expired_token_is_not_active() -> None:
    t = RefreshToken(
        id=RefreshTokenId(uuid4()),
        user_id=UserId(uuid4()),
        token_hash="0" * 64,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert t.is_expired is True
    assert t.is_active is False


def test_rotate_marks_old_token_and_links_replacement() -> None:
    old = _make_token()
    new = _make_token()
    old.rotate_to(new)
    assert old.status == TokenStatus.ROTATED
    assert old.replaced_by_id == new.id
    assert old.revoked_at is not None


def test_revoke_is_idempotent() -> None:
    t = _make_token()
    t.revoke()
    first_revoke = t.revoked_at
    t.revoke()
    assert t.status == TokenStatus.REVOKED
    assert t.revoked_at == first_revoke
