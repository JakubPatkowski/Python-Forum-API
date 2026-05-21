"""Shared domain primitives (Entity, ValueObject, EntityId, DomainEvent, errors)."""

from app.shared.domain.entity import AggregateRoot, Entity
from app.shared.domain.entity_id import EntityId
from app.shared.domain.errors import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    UnauthenticatedError,
    ValidationError,
)
from app.shared.domain.events import DomainEvent
from app.shared.domain.value_object import ValueObject

__all__ = [
    "AggregateRoot",
    "ConflictError",
    "DomainError",
    "DomainEvent",
    "Entity",
    "EntityId",
    "NotFoundError",
    "PermissionDeniedError",
    "UnauthenticatedError",
    "ValidationError",
    "ValueObject",
]
