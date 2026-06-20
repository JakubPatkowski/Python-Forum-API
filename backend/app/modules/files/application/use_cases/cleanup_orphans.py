"""Delete orphaned (standalone, never-attached) files past the retention window.

A file is created STANDALONE on upload and only becomes owned once attached to
a post/comment/avatar/category. If the user changes their mind, the row and its
objects linger — this use case purges them. Driven by the maintenance CLI /
k8s CronJob.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.files.application.ports import IFileStorage, IFilesUnitOfWork
from app.shared.application.event_bus import IEventBus
from app.shared.application.result import Ok, Result
from app.shared.domain.errors import DomainError


class CleanupOrphansUseCase:
    """Remove standalone files older than ``retention_hours``.

    Processes up to ``batch_size`` files per call; the caller loops until the
    returned count is zero.
    """

    def __init__(self, uow: IFilesUnitOfWork, storage: IFileStorage, bus: IEventBus) -> None:
        self._uow = uow
        self._storage = storage
        self._bus = bus

    async def execute(
        self, *, retention_hours: int, batch_size: int = 100
    ) -> Result[int, DomainError]:
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)

        all_keys: list[str] = []
        events = []
        async with self._uow as uow:
            orphans = await uow.files.list_orphans(older_than=cutoff, limit=batch_size)
            for file in orphans:
                all_keys.extend(file.all_storage_keys())
                file.record_deletion()
                await uow.files.remove(file)
                events.extend(file.pull_events())
            await uow.commit()

        if all_keys:
            await self._storage.remove_many(all_keys)
        for event in events:
            await self._bus.publish(event)
        return Ok(len(orphans))
