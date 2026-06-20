# Development

## Local setup

**Backend** (from `backend/`):

```bash
uv sync                                   # install dependencies
uv run alembic upgrade head               # apply migrations
uv run uvicorn app.main:app --reload      # run the API (Swagger at /docs)
```

**Frontend** (from `frontend/`):

```bash
pnpm install
pnpm dev
```

**Full stack** (Postgres + MinIO + backend):

```bash
docker compose up --build
```

After a schema change on an existing volume, reset first:
`docker compose down -v`.

## Code conventions

- **Strong typing** throughout: `X | Y` / `X | None`, lowercase collections, `mypy --strict`, ruff (E, F, I, B, UP, N, S, ASYNC, SIM, C4).
- **Clean Architecture:** business logic lives in `use_cases/`, not routers. Routers stay thin (DTO ↔ command, `_raise_if_error`).
- Use cases return `Result[T, DomainError]`; a global handler maps `DomainError` to HTTP using the envelope `{error: {code, message, field}}`.
- **Pydantic v2** (`model_config={"from_attributes": True}`), `Annotated[..., Depends()]`, explicit status codes (201 / 204 / 415).
- Validation order: 404 (not found) → 403 (forbidden) → 422 / 400 (bad data).
- Identifiers and comments are in English. Domain events are recorded in aggregates (`record_event` + `pull_events`).
- Permissions are enforced in the presentation layer (`Depends(requires("post.create"))`); ownership (author vs `*.any`) is enforced in the use case.

## Pitfalls

Hard-won notes specific to this codebase:

1. **Alembic + volume:** after any schema change in dev, run `docker compose down -v` (or, in Kubernetes, `kubectl delete pvc postgres-pvc -n forum-wedkarskie`). Migration `0001` has a `DuplicateTable` guard, but it is a safety net, not a license to skip the reset.
2. **New ORM table:** add the import of its ORM package to `alembic/env.py`, otherwise `--autogenerate` will emit a spurious `DROP`.
3. **CORS + cookies:** never combine `allow_origins=["*"]` with `allow_credentials=True`. Always list explicit origins.
4. **Postgres dialect types** (`postgresql.ENUM`, `TSVECTOR`, `INET`, `UUID`): create them with the `0002` / `0004` pattern (`create_type=False` + `.create(bind, checkfirst=True)`), with an `else` branch for the SQLite test database.
5. **ORM index naming:** `index=True` generates `ix_*` names from the naming convention in `shared/.../db/base.py`. Use the same names in migrations so autogenerate does not drift.
6. **Legacy ↔ new roles:** any role change must go through the `User` aggregate + repository so the admin panel and RBAC stay consistent.
7. **`expire_on_commit=False`** is set — ORM objects remain usable after `commit()`.

## Open decisions

- **Async vs sync DB access.** Repositories are `async def` over a synchronous `Session`, which blocks the event loop under load. Resolving this (either a real `AsyncSession` stack, or `def` endpoints on FastAPI's threadpool) is a prerequisite for a clean RabbitMQ / WebSocket phase.

## Roadmap

| Status | Item |
|--------|------|
| ⬜ | **CI/CD** — GitHub Actions (ruff + mypy + pytest + image builds) |
| 🟡 | **Frontend polish** — "my files" gallery, attachment management in edit, tag/category management UI |
| ⬜ | **RabbitMQ + notifications + audit** — domain events across processes (depends on the async decision above) |
| ⬜ | **WebSocket** — live updates; the frontend is ready (just `invalidateQueries` on the relevant query keys) |
| 🟡 | **Additional DB views** — forum / category statistics for dashboards |
| 🟡 | **Observability polish** — request-id middleware, tracing |

See also: [Architecture](./01-architecture.md) · [Testing](./06-testing.md).
