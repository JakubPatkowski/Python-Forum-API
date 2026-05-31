"""Files ORM. Importing this module registers ``FileOrm`` on ``Base.metadata``
(required by ``alembic/env.py`` so autogenerate sees the table)."""

from app.modules.files.infrastructure.orm.file_orm import FileOrm

__all__ = ["FileOrm"]
