"""SQLAlchemy mapping for ``posts``.

The legacy :class:`app.models.post.Post` already maps the table and keeps
legacy columns alive for any code that still touches them. We re-export
it as ``PostOrm`` so phase-2 code reads cleanly. New phase-2 columns
(``public_id``, ``slug``, ``is_deleted``, ``search_tsv``) live on the
same class — see :mod:`app.models.post`.
"""

from __future__ import annotations

from app.models.post import Post as _LegacyPostModel

# Public alias — phase-2 code should refer to this name only.
PostOrm = _LegacyPostModel
