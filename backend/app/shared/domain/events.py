"""Domain events — base class.

Concrete events should subclass `DomainEvent` and add fields:

    @dataclass(frozen=True, slots=True)
    class UserRegistered(DomainEvent):
        user_id: UserId
        email: str
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events.

    Identity is `event_id`; `occurred_at` is the wall-clock time the event
    was created (UTC).
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
