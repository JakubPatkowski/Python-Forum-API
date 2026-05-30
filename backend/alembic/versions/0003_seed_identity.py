"""seed identity catalogue (phase 1)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-22 00:00:00.000000

Seeds the permission catalogue and predefined role bundles (user /
moderator / admin). Idempotent — re-running ``alembic upgrade head`` does
not duplicate rows. Existing users are backfilled into the ``user_roles``
table according to their legacy ``users.role`` enum value.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Must match :mod:`app.modules.identity.domain.permission`. Duplicated here
# so the migration stands on its own and never imports application code.
PERMISSION_CODES: tuple[str, ...] = (
    "post.read",
    "post.create",
    "post.update.own",
    "post.update.any",
    "post.delete.own",
    "post.delete.any",
    "comment.read",
    "comment.create",
    "comment.update.own",
    "comment.update.any",
    "comment.delete.own",
    "comment.delete.any",
    "file.upload",
    "file.download",
    "file.delete.own",
    "file.delete.any",
    "category.manage",
    "tag.manage",
    "user.read.any",
    "user.manage",
    "role.manage",
    "audit.read",
)

_USER = (
    "post.read",
    "post.create",
    "post.update.own",
    "post.delete.own",
    "comment.read",
    "comment.create",
    "comment.update.own",
    "comment.delete.own",
    "file.upload",
    "file.download",
    "file.delete.own",
)
_MOD_EXTRA = (
    "post.update.any",
    "post.delete.any",
    "comment.update.any",
    "comment.delete.any",
    "file.delete.any",
    "category.manage",
    "tag.manage",
)
_ADMIN_EXTRA = (
    "user.read.any",
    "user.manage",
    "role.manage",
    "audit.read",
)

ROLE_BUNDLES: dict[str, tuple[str, ...]] = {
    "user": _USER,
    "moderator": _USER + _MOD_EXTRA,
    "admin": _USER + _MOD_EXTRA + _ADMIN_EXTRA,
}


def upgrade() -> None:
    bind = op.get_bind()

    # --- permissions --------------------------------------------------------
    for code in PERMISSION_CODES:
        bind.execute(
            sa.text(
                "INSERT INTO permissions (code) VALUES (:code) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code},
        )

    # --- roles --------------------------------------------------------------
    for role_name in ROLE_BUNDLES:
        bind.execute(
            sa.text(
                "INSERT INTO roles (name) VALUES (:name) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"name": role_name},
        )

    # --- role_permissions ---------------------------------------------------
    for role_name, codes in ROLE_BUNDLES.items():
        role_id = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :n"), {"n": role_name}
        ).scalar_one()
        for code in codes:
            permission_id = bind.execute(
                sa.text("SELECT id FROM permissions WHERE code = :c"),
                {"c": code},
            ).scalar_one()
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:rid, :pid) ON CONFLICT DO NOTHING"
                ),
                {"rid": role_id, "pid": permission_id},
            )

    # --- backfill user_roles from legacy ``users.role`` --------------------
    # Each existing user gets the matching phase-1 role assignment so legacy
    # accounts keep working with the new RBAC tables.
    # Guard: the ``role`` column only exists when 0001 ran on a *fresh* DB
    # (the baseline guard skips CREATE TABLE when ``users`` already existed,
    # so older volumes may not have it).
    has_role_col = "role" in {
        c["name"] for c in sa.inspect(bind).get_columns("users")
    }
    if has_role_col:
        bind.execute(
            sa.text(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT u.id, r.id
                FROM users u
                JOIN roles r ON r.name = u.role::text
                ON CONFLICT DO NOTHING
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM user_roles"))
    bind.execute(sa.text("DELETE FROM role_permissions"))
    bind.execute(sa.text("DELETE FROM roles"))
    bind.execute(sa.text("DELETE FROM permissions"))
