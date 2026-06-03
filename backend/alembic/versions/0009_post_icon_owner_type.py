"""add post_icon value to file_owner_type enum (thread icons)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-01 00:00:00.000000

Wątki dostają własną ikonę. Ikona to plik w tabeli ``files`` z nowym
``owner_type = 'post_icon'`` wskazujący na ``owner_post_id`` (ten sam FK co
załączniki, ale inny typ — nie miesza się z galerią załączników wątku).

Postgres: rozszerzamy enum ``file_owner_type`` o wartość ``post_icon``.
SQLite (testy): ``owner_type`` trzymane jako tekst, więc no-op.
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
        # IF NOT EXISTS chroni przed błędem przy ponownym uruchomieniu.
        op.execute("ALTER TYPE file_owner_type ADD VALUE IF NOT EXISTS 'post_icon'")
    # SQLite: enum to zwykły VARCHAR — brak zmiany schematu.


def downgrade() -> None:
    # Postgres nie wspiera usuwania wartości z enuma bez przebudowy typu.
    # Wartość 'post_icon' jest nieszkodliwa, więc downgrade jest no-op.
    pass
