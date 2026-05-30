"""create content tables (phase 2)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-29 00:00:00.000000

Phase-2 schema additions for the modular ``content`` module:

* ``categories``: add ``public_id`` (UUID), ``slug``, ``created_at``.
* ``posts``: add ``public_id``, ``slug``, ``is_deleted``, ``search_tsv``
  (Postgres full-text vector populated by a trigger).
* ``comments``: add ``public_id``, ``path`` (materialized path), ``is_deleted``,
  ``updated_at``.
* New ``tags`` and ``post_tags`` tables.

All additions are backwards compatible — legacy columns stay as-is, so the
legacy attachments router and admin SSR keep working until phase 3 removes
them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        uuid_type: sa.types.TypeEngine = postgresql.UUID(as_uuid=True)
        tsv_type: sa.types.TypeEngine = postgresql.TSVECTOR()
    else:  # pragma: no cover — sqlite fallback for tests only
        uuid_type = sa.String(length=36)
        tsv_type = sa.Text()

    # --- categories: phase-2 columns ---------------------------------------
    with op.batch_alter_table("categories") as batch:
        batch.add_column(sa.Column("public_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("slug", sa.String(length=120), nullable=True))
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            )
        )

    # Backfill existing rows.
    if is_postgres:
        op.execute(
            "UPDATE categories SET public_id = gen_random_uuid() "
            "WHERE public_id IS NULL"
        )
        # Naive slug derived from the name — strips non-alphanumerics. Polish
        # diacritics survive as hyphens; new categories should be created with
        # the domain's :class:`Slug.from_text` helper instead.
        op.execute(
            """
            UPDATE categories
            SET slug = trim(both '-' from regexp_replace(
                lower(name), '[^a-z0-9]+', '-', 'g'
            ))
            WHERE slug IS NULL
            """
        )
        # Fall back to ``cat-<id>`` if the derivation produced an empty slug.
        op.execute(
            "UPDATE categories SET slug = 'cat-' || id::text "
            "WHERE slug IS NULL OR slug = ''"
        )
    op.create_unique_constraint(
        "uq_categories_public_id", "categories", ["public_id"]
    )
    op.create_index("ix_categories_public_id", "categories", ["public_id"])
    op.create_unique_constraint("uq_categories_slug", "categories", ["slug"])
    op.create_index("ix_categories_slug", "categories", ["slug"])

    # --- posts: phase-2 columns --------------------------------------------
    with op.batch_alter_table("posts") as batch:
        batch.add_column(sa.Column("public_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("slug", sa.String(length=220), nullable=True))
        batch.add_column(
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("search_tsv", tsv_type, nullable=True))

    if is_postgres:
        op.execute(
            "UPDATE posts SET public_id = gen_random_uuid() WHERE public_id IS NULL"
        )
        # Slug derived from the title; append the post id so duplicate titles
        # don't clash within the same author. Diacritics simply fold to hyphens.
        op.execute(
            """
            UPDATE posts SET slug =
                trim(both '-' from regexp_replace(
                    lower(title), '[^a-z0-9]+', '-', 'g'
                )) || '-' || id::text
            WHERE slug IS NULL
            """
        )
        op.execute(
            "UPDATE posts SET slug = 'post-' || id::text "
            "WHERE slug IS NULL OR slug = ''"
        )
    op.create_unique_constraint("uq_posts_public_id", "posts", ["public_id"])
    op.create_index("ix_posts_public_id", "posts", ["public_id"])
    op.create_index("ix_posts_slug", "posts", ["slug"])
    op.create_index(
        "ix_posts_created_at_public_id",
        "posts",
        ["created_at", "public_id"],
        postgresql_using="btree",
    )

    # --- posts: full-text search trigger ----------------------------------
    if is_postgres:
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_posts_search_tsv
            ON posts USING GIN (search_tsv)
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION posts_search_tsv_trigger() RETURNS trigger AS $$
            BEGIN
                NEW.search_tsv :=
                    setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
                RETURN NEW;
            END
            $$ LANGUAGE plpgsql
            """
        )
        op.execute("DROP TRIGGER IF EXISTS posts_search_tsv_update ON posts")
        op.execute(
            """
            CREATE TRIGGER posts_search_tsv_update
            BEFORE INSERT OR UPDATE OF title, content ON posts
            FOR EACH ROW EXECUTE FUNCTION posts_search_tsv_trigger()
            """
        )
        op.execute(
            "UPDATE posts SET title = title WHERE search_tsv IS NULL"
        )

    # --- comments: phase-2 columns -----------------------------------------
    with op.batch_alter_table("comments") as batch:
        batch.add_column(sa.Column("public_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("path", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            )
        )

    if is_postgres:
        op.execute(
            "UPDATE comments SET public_id = gen_random_uuid() WHERE public_id IS NULL"
        )
        # Build the materialised path for existing rows: top-level rows get
        # their own id padded; nested rows still need migration glue, but the
        # legacy code only ever produced top-level comments, so the simple
        # ``lpad`` is enough for backfill.
        op.execute(
            """
            UPDATE comments
            SET path = lpad(id::text, 8, '0')
            WHERE path IS NULL AND parent_id IS NULL
            """
        )
        # Nested legacy comments: build path recursively.
        op.execute(
            """
            WITH RECURSIVE tree AS (
                SELECT id, parent_id, lpad(id::text, 8, '0') AS path
                FROM comments
                WHERE parent_id IS NULL
                UNION ALL
                SELECT c.id, c.parent_id, t.path || '.' || lpad(c.id::text, 8, '0')
                FROM comments c
                JOIN tree t ON c.parent_id = t.id
            )
            UPDATE comments SET path = tree.path
            FROM tree
            WHERE comments.id = tree.id AND comments.path IS NULL
            """
        )
    op.create_unique_constraint(
        "uq_comments_public_id", "comments", ["public_id"]
    )
    op.create_index("ix_comments_public_id", "comments", ["public_id"])
    op.create_index("ix_comments_path", "comments", ["path"])
    op.create_index(
        "ix_comments_post_id_path", "comments", ["post_id", "path"]
    )

    # --- tags ---------------------------------------------------------------
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("public_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("public_id", name="uq_tags_public_id"),
        sa.UniqueConstraint("name", name="uq_tags_name"),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )
    op.create_index("ix_tags_public_id", "tags", ["public_id"])
    op.create_index("ix_tags_name", "tags", ["name"])
    op.create_index("ix_tags_slug", "tags", ["slug"])

    # --- post_tags ----------------------------------------------------------
    op.create_table(
        "post_tags",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("post_id", "tag_id", name="pk_post_tags"),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_post_tags_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_post_tags_tag_id_tags",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_post_tags_post_id", "post_tags", ["post_id"])
    op.create_index("ix_post_tags_tag_id", "post_tags", ["tag_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index("ix_post_tags_tag_id", table_name="post_tags")
    op.drop_index("ix_post_tags_post_id", table_name="post_tags")
    op.drop_table("post_tags")

    op.drop_index("ix_tags_slug", table_name="tags")
    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_index("ix_tags_public_id", table_name="tags")
    op.drop_table("tags")

    op.drop_index("ix_comments_post_id_path", table_name="comments")
    op.drop_index("ix_comments_path", table_name="comments")
    op.drop_index("ix_comments_public_id", table_name="comments")
    op.drop_constraint(
        "uq_comments_public_id", "comments", type_="unique"
    )
    with op.batch_alter_table("comments") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("is_deleted")
        batch.drop_column("path")
        batch.drop_column("public_id")

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS posts_search_tsv_update ON posts")
        op.execute("DROP FUNCTION IF EXISTS posts_search_tsv_trigger()")
        op.execute("DROP INDEX IF EXISTS ix_posts_search_tsv")

    op.drop_index("ix_posts_created_at_public_id", table_name="posts")
    op.drop_index("ix_posts_slug", table_name="posts")
    op.drop_index("ix_posts_public_id", table_name="posts")
    op.drop_constraint("uq_posts_public_id", "posts", type_="unique")
    with op.batch_alter_table("posts") as batch:
        batch.drop_column("search_tsv")
        batch.drop_column("is_deleted")
        batch.drop_column("slug")
        batch.drop_column("public_id")

    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_constraint("uq_categories_slug", "categories", type_="unique")
    op.drop_index("ix_categories_public_id", table_name="categories")
    op.drop_constraint(
        "uq_categories_public_id", "categories", type_="unique"
    )
    with op.batch_alter_table("categories") as batch:
        batch.drop_column("created_at")
        batch.drop_column("slug")
        batch.drop_column("public_id")
