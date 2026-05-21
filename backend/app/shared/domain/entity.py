"""Entity and AggregateRoot base classes.

`Entity` has identity (compared by `id`).
`AggregateRoot` additionally records domain events that should be published
after the aggregate is persisted.
"""

from __future__ import annotations

from app.shared.domain.entity_id import EntityId
from app.shared.domain.events import DomainEvent


class Entity[ID: EntityId]:
    """Base class for entities. Identity-based equality."""

    id: ID

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class AggregateRoot[ID: EntityId](Entity[ID]):
    """Aggregate root — entry point for an aggregate boundary.

    Aggregate roots record domain events that callers (use cases) should
    publish to the event bus after the unit of work commits.
    """

    def __init__(self) -> None:
        self._pending_events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        """Append a domain event to be published after persistence."""
        self._pending_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Return queued events and clear the internal buffer.

        Call this exactly once, after `uow.commit()` succeeded.
        """
        events, self._pending_events = self._pending_events, []
        return events
