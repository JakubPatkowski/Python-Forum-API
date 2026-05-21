# Alembic migrations

This directory holds versioned schema migrations.

## Common commands

```bash
# Create new revision from current ORM models vs. live DB schema.
uv run alembic revision --autogenerate -m "add foo"

# Apply all pending migrations.
uv run alembic upgrade head

# Move back one revision.
uv run alembic downgrade -1

# Show current revision in DB.
uv run alembic current

# Show history.
uv run alembic history --verbose
```

## Conventions

- File template: `<revision>_<slug>.py`, slug in English snake_case.
- Each migration is reversible — `downgrade()` must be implemented.
- Schema-only migrations and data backfills go in **separate** revisions
  whenever feasible, so a rollback does not have to undo data changes.
- Naming convention for indexes / constraints is set in
  `app.shared.infrastructure.db.base` and applied automatically.

## Baseline

`0001_baseline.py` recreates the schema produced by the legacy
`Base.metadata.create_all` call from `app/main.py`. From phase 1 onwards
every change goes through Alembic.
