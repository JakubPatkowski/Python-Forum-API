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
# vs. Postgres max_connections -- values are configurable via env (see
# config.py: DB_POOL_*; the budget is sized against HPA maxReplicas).
engine: Final[Engine] = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
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
