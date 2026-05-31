"""create files table + avatar FK, drop legacy attachments (phase 3)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-31 00:00:00.000000

Phase-3 ``files`` module:

* new ``files`` table — generic metadata for every uploaded object (bytes live
  in MinIO, addressed by ``storage_key``). Polymorphic ownership via
  ``owner_type`` + one of ``owner_{post,comment,user,category}_id``.
* ``file_owner_type`` / ``file_status`` Postgres enums.
* FK ``users.avatar_file_id -> files.id`` (ON DELETE SET NULL) — deleting an
  avatar file clears the user's avatar automatically.
* drops the legacy ``attachments`` table (replaced by ``files``).

Dialect-aware (Postgres enums/JSON, SQLite fallbacks for tests), following the
pattern established in 0002/0004.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWNER_VALUES = ("standalone", "post", "comment", "user_avatar", "category")
_STATUS_VALUES = ("pending", "ready")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        uuid_type: sa.types.TypeEngine = postgresql.UUID(as_uuid=True)
        owner_enum: sa.types.TypeEngine = postgresql.ENUM(
            *_OWNER_VALUES, name="file_owner_type", create_type=False
        )
        status_enum: sa.types.TypeEngine = postgresql.ENUM(
            *_STATUS_VALUES, name="file_status", create_type=False
        )
        owner_enum.create(bind, checkfirst=True)
        status_enum.create(bind, checkfirst=True)
    else:  # pragma: no cover - sqlite fallback for tests only
        uuid_type = sa.String(length=36)
        owner_enum = sa.String(length=20)
        status_enum = sa.String(length=12)

    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("public_id", uuid_type, nullable=False),
        sa.Column("uploader_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column(
            "size_bytes", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status", status_enum, nullable=False, server_default="pending"
        ),
        sa.Column(
            "owner_type", owner_enum, nullable=False, server_default="standalone"
        ),
        sa.Column("owner_post_id", sa.Integer(), nullable=True),
        sa.Column("owner_comment_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("owner_category_id", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("variants", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_files"),
        sa.UniqueConstraint("public_id", name="uq_files_public_id"),
        sa.UniqueConstraint("storage_key", name="uq_files_storage_key"),
        sa.ForeignKeyConstraint(
            ["uploader_id"], ["users.id"],
            name="fk_files_uploader_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_post_id"], ["posts.id"],
            name="fk_files_owner_post_id_posts", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_comment_id"], ["comments.id"],
            name="fk_files_owner_comment_id_comments", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"],
            name="fk_files_owner_user_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_category_id"], ["categories.id"],
            name="fk_files_owner_category_id_categories", ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "(CASE WHEN owner_post_id     IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN owner_comment_id  IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN owner_user_id     IS NOT NULL THEN 1 ELSE 0 END) "
            "+ (CASE WHEN owner_category_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
            name="ck_files_owner_single",
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_files_size_nonneg"),
    )

    op.create_index("ix_files_public_id", "files", ["public_id"], unique=False)
    op.create_index("ix_files_uploader_id", "files", ["uploader_id"])
    op.create_index("ix_files_sha256", "files", ["sha256"])
    op.create_index("ix_files_owner_type", "files", ["owner_type"])
    op.create_index("ix_files_created_at", "files", ["created_at"])
    op.create_index("ix_files_owner_post_id", "files", ["owner_post_id"])
    op.create_index("ix_files_owner_comment_id", "files", ["owner_comment_id"])
    op.create_index("ix_files_owner_user_id", "files", ["owner_user_id"])
    op.create_index("ix_files_owner_category_id", "files", ["owner_category_id"])

    # FK: users.avatar_file_id -> files.id (column already exists since phase 1).
    # SQLite cannot ALTER ADD FK without table rebuild; skip there (tests).
    if is_postgres:
        op.create_foreign_key(
            "fk_users_avatar_file_id_files",
            "users",
            "files",
            ["avatar_file_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Drop the legacy attachments table (superseded by files).
    if sa.inspect(bind).has_table("attachments"):
        op.drop_table("attachments")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Recreate the legacy attachments table (best-effort reversibility).
    if not sa.inspect(bind).has_table("attachments"):
        op.create_table(
            "attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column(
                "stored_filename", sa.String(length=255), nullable=False, unique=True
            ),
            sa.Column("content_type", sa.String(length=100), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("uploader_id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=True),
            sa.Column("comment_id", sa.Integer(), nullable=True),
        )

    if is_postgres:
        op.drop_constraint(
            "fk_users_avatar_file_id_files", "users", type_="foreignkey"
        )

    for idx in (
        "ix_files_owner_category_id",
        "ix_files_owner_user_id",
        "ix_files_owner_comment_id",
        "ix_files_owner_post_id",
        "ix_files_created_at",
        "ix_files_owner_type",
        "ix_files_sha256",
        "ix_files_uploader_id",
        "ix_files_public_id",
    ):
        op.drop_index(idx, table_name="files")
    op.drop_table("files")

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS file_status")
        op.execute("DROP TYPE IF EXISTS file_owner_type")
