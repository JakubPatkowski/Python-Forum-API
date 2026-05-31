"""Delete orphaned (standalone, never-attached) files past retention.

Why this exists: the upload endpoint hands the client a file id *before* the
file is referenced by a post/comment/avatar/category. If the user abandons the
draft, the file stays ``STANDALONE`` forever. This job purges such files
(DB row + the original object + thumbnails in MinIO).

Run locally / in docker-compose::

    python -m app.maintenance.cleanup_orphan_files

In Kubernetes it runs as a daily CronJob (see k8s/backend/cleanup-cronjob.yaml).
The retention window is ``settings.FILE_ORPHAN_RETENTION_HOURS``.
"""

from __future__ import annotations

import asyncio

import structlog

from app.config import settings
from app.container import get_cleanup_orphans_uc
from app.shared.application.result import Ok
from app.shared.infrastructure.logging import configure_logging

logger = structlog.get_logger(__name__)

_BATCH_SIZE = 100


async def run_cleanup() -> int:
    """Delete orphans in batches until none remain; return the total removed."""
    total = 0
    while True:
        uc = get_cleanup_orphans_uc()  # fresh UoW (DB session) per batch
        result = await uc.execute(
            retention_hours=settings.FILE_ORPHAN_RETENTION_HOURS,
            batch_size=_BATCH_SIZE,
        )
        count = result.value if isinstance(result, Ok) else 0
        total += count
        if count < _BATCH_SIZE:
            break
    logger.info(
        "orphan_cleanup_done",
        deleted=total,
        retention_hours=settings.FILE_ORPHAN_RETENTION_HOURS,
    )
    return total


def main() -> None:
    configure_logging(level="DEBUG" if settings.DEBUG else "INFO")
    deleted = asyncio.run(run_cleanup())
    print(f"Deleted {deleted} orphan file(s).")


if __name__ == "__main__":
    main()
