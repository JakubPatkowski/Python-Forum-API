"""SQLAlchemy repositories for the files module."""

from app.modules.files.infrastructure.repositories.file_repo import (
    SqlAlchemyFileRepository,
)

__all__ = ["SqlAlchemyFileRepository"]
