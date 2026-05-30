"""SQLAlchemy mapping for ``categories``.

Re-exports the existing :class:`app.models.category.Category` so phase-2 code
references a stable ``CategoryOrm`` name. Phase-2 added ``public_id``,
``slug`` and ``created_at`` columns.
"""

from __future__ import annotations

from app.models.category import Category as _LegacyCategoryModel

# Public alias — phase-2 code should refer to this name only.
CategoryOrm = _LegacyCategoryModel
