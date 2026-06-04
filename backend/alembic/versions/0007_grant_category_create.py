"""grant category.create to all roles (phase F-frontend)

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-31 00:00:00.000000

Adds the new ``category.create`` permission to the catalogue and grants it to
every predefined role (``user`` / ``moderator`` / ``admin``). Decyzja produktowa:
każdy zalogowany użytkownik może założyć nową kategorię; usuwanie kategorii nadal
wymaga ``category.manage`` (moderator+). Idempotentne (``ON CONFLICT DO NOTHING``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_PERMISSION = "category.create"
# Wszystkie predefiniowane role dostają nowe uprawnienie.
_ROLES_WITH_PERMISSION: tuple[str, ...] = ("user", "moderator", "admin")


def upgrade() -> None:
    bind = op.get_bind()

    # --- permission ---------------------------------------------------------
    bind.execute(
        sa.text(
            "INSERT INTO permissions (code) VALUES (:code) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"code": _NEW_PERMISSION},
    )

    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE code = :c"),
        {"c": _NEW_PERMISSION},
    ).scalar_one()

    # --- grant to roles -----------------------------------------------------
    for role_name in _ROLES_WITH_PERMISSION:
        role_id = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :n"), {"n": role_name}
        ).scalar_one_or_none()
        if role_id is None:
            continue  # rola nie istnieje (np. nietknięta baza) — pomiń
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "VALUES (:rid, :pid) ON CONFLICT DO NOTHING"
            ),
            {"rid": role_id, "pid": permission_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE code = :c"),
        {"c": _NEW_PERMISSION},
    ).scalar_one_or_none()
    if permission_id is None:
        return
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
        {"pid": permission_id},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE id = :pid"),
        {"pid": permission_id},
    )
