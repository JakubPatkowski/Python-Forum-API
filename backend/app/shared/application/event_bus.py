"""Event bus port.

The application layer publishes `DomainEvent` instances through an
`IEventBus`. Implementations: `InMemoryEventBus` (phase 0) and
`RabbitMQEventBus` (phase 4).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.shared.domain.events import DomainEvent

type EventHandler[E: DomainEvent] = Callable[[E], Awaitable[None]]


class IEventBus(Protocol):
    """Publish/subscribe contract for domain events."""

    async def publish(self, event: DomainEvent) -> None: ...

    def subscribe[E: DomainEvent](
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None: ...

    async def start(self) -> None:
        """Start any background workers (no-op for in-memory)."""

    async def stop(self) -> None:
        """Tear down workers / connections."""
