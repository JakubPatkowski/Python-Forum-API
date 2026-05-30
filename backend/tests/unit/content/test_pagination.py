"""Unit tests for the post cursor codec."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.content.application.errors import InvalidCursor
from app.modules.content.application.pagination import PostCursor


class TestPostCursor:
    def test_roundtrip(self) -> None:
        ts = datetime(2026, 5, 1, 12, 30, 0, tzinfo=UTC)
        pid = uuid4()
        encoded = PostCursor(created_at=ts, public_id=pid).encode()
        decoded = PostCursor.decode(encoded)
        assert decoded.created_at == ts
        assert decoded.public_id == pid

    def test_encoded_is_url_safe(self) -> None:
        c = PostCursor(
            created_at=datetime.now(UTC), public_id=uuid4()
        ).encode()
        # No padding, no plus/slash characters.
        assert "=" not in c
        assert "+" not in c
        assert "/" not in c

    def test_decode_rejects_garbage(self) -> None:
        with pytest.raises(InvalidCursor):
            PostCursor.decode("not-a-cursor")

    def test_decode_rejects_truncated(self) -> None:
        good = PostCursor(
            created_at=datetime.now(UTC), public_id=uuid4()
        ).encode()
        with pytest.raises(InvalidCursor):
            PostCursor.decode(good[:5])
