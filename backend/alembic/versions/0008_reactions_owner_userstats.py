"""reactions table + category owner + user_stats view (engagement phase)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-01 00:00:00.000000

Three changes for "engagement" and statistics:

* ``categories.owner_id`` (FK users, nullable) -- category creator; lets a
  regular user manage the icon of THEIR OWN category.
* ``reactions`` -- likes on posts and comments. Polymorphic target via
  ``target_type`` + ``target_id`` (int FK to posts/comments -- no hard FK,
  because target_type distinguishes the table). Unique ``(user_id, target_type, target_id)``.
* ``user_stats`` view -- aggregate of user statistics (posts, comments, likes
  received, join date). Aligned with "Phase 6 -- DB views"; no new table to
  maintain, computed on the fly.

Dialect-aware (Postgres + a SQLite branch for tests), pattern from 0002/0004/0006.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TARGET_VALUES = ("post", "comment")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)

    # --- categories.owner_id ------------------------------------------------
    cat_cols = {c["name"] for c in inspector.get_columns("categories")}
    if "owner_id" not in cat_cols:
        op.add_column(
            "categories",
            sa.Column("owner_id", sa.Integer(), nullable=True),
        )
        # FK added separately so SQLite (batch-less) doesn't blow up
        if is_postgres:
            op.create_foreign_key(
                "fk_categories_owner_id_users",
                "categories",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # --- reactions ----------------------------------------------------------
    if not inspector.has_table("reactions"):
        target_type_type: sa.types.TypeEngine
        if is_postgres:
            target_type_type = sa.Enum(
                *_TARGET_VALUES, name="reaction_target_type", create_type=True
            )
        else:
            target_type_type = sa.String(length=16)

        op.create_table(
            "reactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("target_type", target_type_type, nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "user_id", "target_type", "target_id", name="uq_reaction_once"
            ),
        )
        op.create_index(
            "ix_reactions_target", "reactions", ["target_type", "target_id"]
        )

    # --- user_stats view ----------------------------------------------------
    # Likes received = reactions pointing at the author's posts/comments.
    op.execute("DROP VIEW IF EXISTS user_stats")
    op.execute(
        """
        CREATE VIEW user_stats AS
        SELECT
            u.id          AS user_id,
            u.public_id   AS user_public_id,
            u.created_at  AS joined_at,
            COALESCE(p.cnt, 0)  AS posts_count,
            COALESCE(c.cnt, 0)  AS comments_count,
            COALESCE(lp.cnt, 0) + COALESCE(lc.cnt, 0) AS likes_received
        FROM users u
        LEFT JOIN (
            SELECT author_id, COUNT(*) AS cnt FROM posts
            WHERE is_deleted = false GROUP BY author_id
        ) p ON p.author_id = u.id
        LEFT JOIN (
            SELECT author_id, COUNT(*) AS cnt FROM comments
            WHERE is_deleted = false GROUP BY author_id
        ) c ON c.author_id = u.id
        LEFT JOIN (
            SELECT po.author_id, COUNT(*) AS cnt
            FROM reactions r JOIN posts po ON po.id = r.target_id
            WHERE r.target_type = 'post' GROUP BY po.author_id
        ) lp ON lp.author_id = u.id
        LEFT JOIN (
            SELECT co.author_id, COUNT(*) AS cnt
            FROM reactions r JOIN comments co ON co.id = r.target_id
            WHERE r.target_type = 'comment' GROUP BY co.author_id
        ) lc ON lc.author_id = u.id
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.execute("DROP VIEW IF EXISTS user_stats")

    if sa.inspect(bind).has_table("reactions"):
        op.drop_index("ix_reactions_target", table_name="reactions")
        op.drop_table("reactions")
    if is_postgres:
        op.execute("DROP TYPE IF EXISTS reaction_target_type")

    cat_cols = {c["name"] for c in sa.inspect(bind).get_columns("categories")}
    if "owner_id" in cat_cols:
        if is_postgres:
            op.drop_constraint(
                "fk_categories_owner_id_users", "categories", type_="foreignkey"
            )
        op.drop_column("categories", "owner_id")
