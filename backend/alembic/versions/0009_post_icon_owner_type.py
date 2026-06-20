"""add post_icon value to file_owner_type enum (thread icons)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-01 00:00:00.000000

Threads get their own icon. The icon is a file in the ``files`` table with a new
``owner_type = 'post_icon'`` pointing at ``owner_post_id`` (the same FK as
attachments, but a different type -- it doesn't mix with the thread's attachment gallery).

Postgres: we extend the ``file_owner_type`` enum with the value ``post_icon``.
SQLite (tests): ``owner_type`` is stored as text, so this is a no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # IF NOT EXISTS guards against an error on re-run.
        op.execute("ALTER TYPE file_owner_type ADD VALUE IF NOT EXISTS 'post_icon'")
    # SQLite: the enum is a plain VARCHAR -- no schema change.


def downgrade() -> None:
    # Postgres does not support removing a value from an enum without rebuilding the type.
    # The 'post_icon' value is harmless, so the downgrade is a no-op.
    pass
