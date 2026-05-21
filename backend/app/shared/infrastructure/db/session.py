"""SQLAlchemy engine + session factory + FastAPI dependency `get_db`.

For now we use the synchronous engine so the legacy routers keep working
without modification. Phase 1+ will introduce async sessions module by module.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Final

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Engine is process-wide. Pool size kept moderate for k8s replicas * pool_size
# vs. Postgres max_connections.
engine: Final[Engine] = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal: Final[sessionmaker[Session]] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
