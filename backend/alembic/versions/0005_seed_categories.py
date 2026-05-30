"""seed default categories (phase 2)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29 00:00:00.000000

Seeds the five canonical forum categories (Spinning, Karpiowanie, Muszka,
Sprzęt, Łowiska). Idempotent: each insert is guarded by ``ON CONFLICT``.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (name, slug, description) — slugs are URL-safe ASCII, names keep the
# Polish diacritics.
DEFAULT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("Spinning", "spinning", "Łowienie metodą spinningową — przynęty sztuczne, blachy, woblery."),
    ("Karpiowanie", "karpiowanie", "Karpiowanie — sesyjne, krótkie wypady, sprzęt, zanęty."),
    ("Muszka", "muszka", "Wędkarstwo muchowe — sucha, mokra, nimfa, streamer."),
    ("Sprzęt", "sprzet", "Recenzje, porady i pytania o sprzęt wędkarski."),
    ("Łowiska", "lowiska", "Łowiska komercyjne, rzeki, jeziora — relacje i polecane miejsca."),
)


def upgrade() -> None:
    bind = op.get_bind()
    for name, slug, description in DEFAULT_CATEGORIES:
        # If a row with this slug already exists keep it untouched so a
        # human-edited description isn't overwritten on re-run.
        existing = bind.execute(
            sa.text("SELECT id FROM categories WHERE slug = :slug OR name = :name"),
            {"slug": slug, "name": name},
        ).first()
        if existing is not None:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO categories (public_id, name, slug, description, created_at)
                VALUES (:public_id, :name, :slug, :description, NOW())
                """
            ),
            {
                "public_id": uuid4(),
                "name": name,
                "slug": slug,
                "description": description,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM categories WHERE slug IN :slugs"
        ).bindparams(
            sa.bindparam(
                "slugs", expanding=True, value=[c[1] for c in DEFAULT_CATEGORIES]
            )
        )
    )
