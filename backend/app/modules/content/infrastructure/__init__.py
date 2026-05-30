"""Infrastructure layer for the content module — ORM, repositories, UoW."""

from app.modules.content.infrastructure.unit_of_work import (
    SqlAlchemyContentUnitOfWork,
)

__all__ = ["SqlAlchemyContentUnitOfWork"]
