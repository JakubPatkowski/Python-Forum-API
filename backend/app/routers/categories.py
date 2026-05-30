"""DEPRECATED — phase 2 retired this router.

The replacement lives at
``app.modules.content.presentation.routers.categories`` and is mounted under
``/api/v1/categories``. This stub stays only to make accidental imports fail
loudly instead of silently returning the old implementation.
"""

from __future__ import annotations

raise ImportError(
    "app.routers.categories was removed in phase 2. "
    "Use app.modules.content.presentation.routers.categories instead."
)
