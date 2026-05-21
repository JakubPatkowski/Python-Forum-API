"""Backwards-compatible shim — re-exports the canonical DB primitives.

Legacy modules (`app.models.*`, old `services/`, old `routers/`) import
`Base`, `engine`, `SessionLocal`, `get_db` from here. The canonical
implementation now lives in `app.shared.infrastructure.db`. Keeping this
shim avoids touching legacy code in phase 0 — phases 1-3 will migrate
each module to the new location and this file can then be deleted.
"""

from app.shared.infrastructure.db import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
