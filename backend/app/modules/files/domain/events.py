"""Domain events emitted by the :class:`File` aggregate.

Published on the event bus after the unit of work commits. From phase 4 they
flow through RabbitMQ and are consumed by ``audit`` / ``notifications``.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class FileUploaded(DomainEvent):
    """A file finished uploading and was validated (PENDING → READY)."""

    file_id: UUID
    uploader_id: UUID
    storage_key: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FileAttached(DomainEvent):
    """A file was attached to an owner (post / comment / avatar / category)."""

    file_id: UUID
    owner_type: str
    owner_public_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class FileDetached(DomainEvent):
    """A file was detached from its owner and is standalone again."""

    file_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class FileDeleted(DomainEvent):
    """A file record was deleted. Carries the storage keys to purge."""

    file_id: UUID
    storage_key: str
    variant_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class AvatarChanged(DomainEvent):
    """A user's avatar was set or cleared."""

    user_id: UUID
    file_id: UUID | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryImageChanged(DomainEvent):
    """A category's image was set or cleared."""

    category_id: UUID
    file_id: UUID | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PostIconChanged(DomainEvent):
    """A post's (thread's) icon was set or cleared."""

    post_id: UUID
    file_id: UUID | None
