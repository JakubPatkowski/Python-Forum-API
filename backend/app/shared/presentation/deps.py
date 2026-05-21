"""FastAPI dependency helpers shared across modules.

Concrete authentication / authorization dependencies live in the `identity`
module (phase 1). This file holds only framework glue that has no domain
knowledge.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.shared.infrastructure.db import get_db

# Sugar alias so routers can write `db: DbSession`.
DbSession = Annotated[Session, Depends(get_db)]
