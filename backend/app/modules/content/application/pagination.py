"""Keyset cursor codec for content listings.

Cursors are an opaque base64-url string encoding ``(created_at, public_id)``
of the *last* item from the previous page. The repository orders posts by
``created_at DESC, public_id DESC`` so the next page is everything strictly
older than the cursor.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.content.application.errors import InvalidCursor


@dataclass(frozen=True, slots=True)
class PostCursor:
    """The two fields needed to keyset-paginate the ``posts`` table."""

    created_at: datetime
    public_id: UUID

    def encode(self) -> str:
        payload = json.dumps(
            {
                "ts": self.created_at.isoformat(),
                "id": str(self.public_id),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")

    @classmethod
    def decode(cls, cursor: str) -> PostCursor:
        try:
            # Re-pad for base64 length compatibility.
            padding = "=" * (-len(cursor) % 4)
            raw = base64.urlsafe_b64decode(cursor + padding)
            data = json.loads(raw.decode("utf-8"))
            return cls(
                created_at=datetime.fromisoformat(data["ts"]),
                public_id=UUID(data["id"]),
            )
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise InvalidCursor() from exc
