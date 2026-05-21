"""SQLAlchemy declarative base with a deterministic naming convention.

A stable naming convention prevents Alembic's `--autogenerate` from emitting
spurious "drop constraint X / add constraint Y" diffs caused by different
default names between Postgres and SQLite, or between SQLAlchemy versions.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Project-wide declarative base. Every ORM mapping inherits this."""

    metadata = metadata
