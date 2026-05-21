"""Event bus implementations (in-memory; RabbitMQ added in phase 4)."""

from app.shared.infrastructure.eventbus.in_memory import InMemoryEventBus

__all__ = ["InMemoryEventBus"]
