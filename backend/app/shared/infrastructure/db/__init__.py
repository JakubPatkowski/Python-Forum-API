"""Shared DB infrastructure: declarative Base, engine, session factory."""

from app.shared.infrastructure.db.base import Base, metadata
from app.shared.infrastructure.db.session import SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db", "metadata"]
