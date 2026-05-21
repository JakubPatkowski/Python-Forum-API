"""In-process event bus.

Synchronously dispatches each event to all subscribed handlers. Used:
- in unit/integration tests,
- as a default during phases 0-3 before RabbitMQ is wired in (phase 4).

Handlers run sequentially; a failing handler logs but does not stop the others.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from app.shared.application.event_bus import EventHandler, IEventBus
from app.shared.domain.events import DomainEvent

logger = structlog.get_logger(__name__)


# Internal storage keeps the handlers loosely typed (`Any`) so different
# `EventHandler[E]` types can coexist in one dict. Type-safety is enforced
# at `subscribe` and `publish` boundaries via the `IEventBus` protocol.
_AnyHandler = Callable[[Any], Awaitable[None]]


class InMemoryEventBus(IEventBus):
    """Pub/sub bus that lives in the current Python process."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[_AnyHandler]] = {}

    def subscribe[E: DomainEvent](
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "event_handler_failed",
                    event_type=type(event).__name__,
                    handler=getattr(handler, "__qualname__", repr(handler)),
                )

    async def start(self) -> None:  # pragma: no cover - no-op
        return None

    async def stop(self) -> None:  # pragma: no cover - no-op
        return None
