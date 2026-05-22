"""DEPRECATED — phase 1 retired this router.

The replacement lives at
``app.modules.identity.presentation.routers.users`` and is mounted under
``/api/v1/users``. This stub stays only to make accidental imports fail
loudly instead of silently returning the old implementation.
"""

from __future__ import annotations

raise ImportError(
    "app.routers.users was removed in phase 1. "
    "Use app.modules.identity.presentation.routers.users instead."
)
