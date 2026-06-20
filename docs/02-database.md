# Database

PostgreSQL 16, accessed through SQLAlchemy 2.0 with the **psycopg3** driver
(`postgresql+psycopg://`). The schema is managed entirely by **Alembic** — there
is no `create_all` at runtime.

## Conventions

- **Internal PK:** `bigserial` (`id` column), never exposed in the API.
- **Public key:** `uuid` v4 in a `public_id` column (`unique not null default gen_random_uuid()`). Ordering uses `(created_at, public_id)`.
- **Timestamps:** `timestamptz`, default `now()`; `updated_at` maintained by the app.
- **Soft delete:** an `is_deleted boolean` column — mandatory for comments so the tree never has gaps.
- **Enums:** Postgres `CREATE TYPE`, created dialect-aware so the SQLite test branch degrades to text.
- **Indexes:** every FK is indexed; partial indexes (`WHERE is_deleted = false`), GIN indexes for `tsvector` and tags.

## Schema by module

### identity

`users`, `roles`, `permissions`, `role_permissions`, `user_roles`,
`user_permissions`, `refresh_tokens`.

- Enums: `user_status('active','blocked','pending_verification')`, `token_status('active','rotated','revoked')`.
- `users.password_hash` holds an Argon2id-encoded hash.
- RBAC is `roles` × `permissions` (many-to-many via `role_permissions`), assigned to users through `user_roles`, with optional per-user overrides in `user_permissions` (grant / deny).
- `refresh_tokens` is a whitelist enabling rotation, reuse detection, and "log out everywhere".

### content

`categories`, `tags`, `posts`, `post_tags`, `comments`.

- Enum: `content_format('plain','markdown')`.
- `comments` use a **materialized path** (`path`, built from `lpad(id, 8, '0')` joined by `.`) plus a cached `depth`; the tree is rendered with `ORDER BY path` (DFS). `MAX_COMMENT_DEPTH = 5`.
- Full-text search is a `tsvector` column kept current by a trigger, with a GIN index.
- Listing uses **keyset pagination** (`?cursor=&limit=`).
- `categories.owner_id` (added in 0008) records the creator, letting a regular user manage their own category's icon.

### files

`files` — a single generic table for every kind of upload.

- Enum `file_owner_type` covers `standalone`, `post`, `comment`, `user_avatar`, `category`, and `post_icon` (the last added in 0009 for thread icons).
- Enum `file_status('pending','ready')`.
- Polymorphic ownership via nullable `owner_post_id` / `owner_comment_id` / `owner_user_id` / `owner_category_id`, each with a partial index, guarded by a `CHECK` constraint. `sha256` is indexed for deduplication.

### engagement

`reactions` and the `user_stats` view (both added in 0008).

- `reactions(user_id, target_type, target_id)` stores likes. The target is polymorphic (`target_type` distinguishes `post` vs `comment`, so there is no hard FK). A unique constraint `uq_reaction_once (user_id, target_type, target_id)` enforces one like per user per target.
- `user_stats` is a **view** (not a table) aggregating posts, comments, likes received, and join date per user — no extra table to maintain.

## Migrations

Alembic revisions `0001`–`0009`:

| Rev | Contents |
|-----|----------|
| 0001 | Baseline (with a `DuplicateTable` guard for legacy volumes) |
| 0002 | identity tables |
| 0003 | seed identity (roles, permissions) |
| 0004 | content tables (+ FTS trigger, path backfill) |
| 0005 | seed default categories |
| 0006 | files table (+ drop of legacy attachments) |
| 0007 | grant `category.create` to all roles |
| 0008 | `reactions`, `categories.owner_id`, `user_stats` view |
| 0009 | `post_icon` value added to `file_owner_type` |

### Migration notes

- New dialect-specific types (`postgresql.ENUM`, `TSVECTOR`, `INET`, `UUID`) follow the pattern in `0002` / `0004`: `create_type=False` + `.create(bind, checkfirst=True)`, with an `else` branch for the SQLite test database.
- After adding a new ORM table, import its ORM package in `alembic/env.py`, otherwise `--autogenerate` will emit a spurious `DROP`.
- In development, after a schema change reset the volume with `docker compose down -v` (or, in Kubernetes, `kubectl delete pvc postgres-pvc -n forum-wedkarskie`) rather than relying on migration self-repair.

See also: [Architecture](./01-architecture.md) · [Security](./03-security.md).
