"""Strongly-typed entity identifiers.

`EntityId[T]` is a phantom-typed wrapper around a UUID. Subclassing with a
specific entity gives a distinct type, so the type checker prevents mixing
`UserId` and `PostId` even though both are UUIDs at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class EntityId[T]:
    """Generic, immutable identifier for a domain entity.

    Usage::

        class UserId(EntityId["User"]): ...

        uid = UserId.new()
        uid2 = UserId(UUID("..."))
    """

    value: UUID

    @classmethod
    def new(cls) -> Self:
        """Generate a new random identifier (UUID v4)."""
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.value)
