"""Alembic environment.

This module is executed by `alembic upgrade`, `alembic revision`, etc.
It wires the project-wide settings, declarative metadata and naming
convention into Alembic so autogenerate produces stable diffs.
"""

from __future__ import annotations

from logging.config import fileConfig

import app.models  # noqa: F401 - side-effect import registers legacy ORM mappers
import app.modules.content.infrastructure.orm  # noqa: F401 - phase-2 mappers (tags, post_tags)
import app.modules.files.infrastructure.orm  # noqa: F401 - phase-3 mappers (files)
import app.modules.identity.infrastructure.orm  # noqa: F401 - phase-1 mappers
from alembic import context
from app.config import settings
from app.shared.infrastructure.db import Base
from sqlalchemy import engine_from_config, pool

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:  # pragma: no cover
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL to stdout)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a real DB via SQLAlchemy engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
