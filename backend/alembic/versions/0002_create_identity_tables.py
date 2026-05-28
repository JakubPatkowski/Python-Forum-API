"""create identity tables (phase 1)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21 00:00:00.000000

Adds the phase-1 RBAC tables (roles, permissions, role_permissions,
user_roles, user_permissions, refresh_tokens) plus the new columns on
``users`` (public_id, password_hash, status enum, avatar_file_id,
updated_at).

Legacy columns on ``users`` (hashed_password, is_active, role) stay until
phase 2 retires the legacy posts/comments/attachments routers.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- ENUM types ---------------------------------------------------------
    if is_postgres:
        user_status_enum = postgresql.ENUM(
            "active", "blocked", "pending_verification", name="user_status"
        )
        token_status_enum = postgresql.ENUM(
            "active", "rotated", "revoked", name="token_status"
        )
        user_status_enum.create(bind, checkfirst=True)
        token_status_enum.create(bind, checkfirst=True)
        status_type: sa.types.TypeEngine = postgresql.ENUM(
            "active",
            "blocked",
            "pending_verification",
            name="user_status",
            create_type=False,
        )
        token_type: sa.types.TypeEngine = postgresql.ENUM(
            "active", "rotated", "revoked", name="token_status", create_type=False
        )
        uuid_type: sa.types.TypeEngine = postgresql.UUID(as_uuid=True)
        inet_type: sa.types.TypeEngine = postgresql.INET()
    else:  # pragma: no cover - SQLite/etc. fallback for tests
        status_type = sa.String(length=32)
        token_type = sa.String(length=16)
        uuid_type = sa.String(length=36)
        inet_type = sa.String(length=45)

    # --- users: add phase-1 columns ----------------------------------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("public_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("status", status_type, nullable=True))
        batch.add_column(sa.Column("avatar_file_id", sa.BigInteger(), nullable=True))
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            )
        )

    # Backfill existing rows.
    if is_postgres:
        op.execute(
            "UPDATE users SET public_id = gen_random_uuid() WHERE public_id IS NULL"
        )
    op.execute("UPDATE users SET password_hash = hashed_password WHERE password_hash IS NULL")
    op.execute(
        "UPDATE users SET status = CASE WHEN is_active THEN 'active'::user_status ELSE 'blocked'::user_status END "
        "WHERE status IS NULL"
    )

    op.create_unique_constraint("uq_users_public_id", "users", ["public_id"])
    op.create_index("ix_users_public_id", "users", ["public_id"])

    # --- roles --------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_name", "roles", ["name"])

    # --- permissions --------------------------------------------------------
    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    # --- role_permissions ---------------------------------------------------
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_role_permissions_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "role_id", "permission_id", name="pk_role_permissions"
        ),
    )

    # --- user_roles ---------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_roles_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_user_roles_role_id_roles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_user_roles_granted_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )

    # --- user_permissions ---------------------------------------------------
    op.create_table(
        "user_permissions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_permissions_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_user_permissions_permission_id_permissions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_user_permissions_granted_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id", "permission_id", name="pk_user_permissions"),
    )

    # --- refresh_tokens -----------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("public_id", uuid_type, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", token_type, nullable=False, server_default="active"),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.BigInteger(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", inet_type, nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by"],
            ["refresh_tokens.id"],
            name="fk_refresh_tokens_replaced_by_refresh_tokens",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("public_id", name="uq_refresh_tokens_public_id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index(
        "ix_refresh_tokens_user_status", "refresh_tokens", ["user_id", "status"]
    )
    op.create_index(
        "ix_refresh_tokens_public_id", "refresh_tokens", ["public_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_public_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_status", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_table("user_permissions")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")

    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_users_public_id", table_name="users")
    op.drop_constraint("uq_users_public_id", "users", type_="unique")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("avatar_file_id")
        batch.drop_column("status")
        batch.drop_column("password_hash")
        batch.drop_column("public_id")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="token_status").drop(bind, checkfirst=True)
        sa.Enum(name="user_status").drop(bind, checkfirst=True)
