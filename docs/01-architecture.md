# Architecture

Forum Wędkarskie is a **modular monolith** built on **Clean Architecture**. One
process, one database, clear module boundaries — cheap to run and deploy, yet
structured so individual modules could be extracted into services later.

## Layered design

The dependency rule points inward: `domain ← application ← infrastructure / presentation`.
The domain layer has no framework imports (no FastAPI, no SQLAlchemy).

| Layer | Responsibility | Examples |
|-------|----------------|----------|
| **domain** | Entities, aggregates, value objects, domain events, business rules | `User`, `Post`, `Comment`, `Slug`, `ContentFormat` |
| **application** | Use cases, ports (Protocols), commands, the `Result` type | `CreatePostUseCase`, `IPostRepository`, `IUnitOfWork` |
| **infrastructure** | Adapters: ORM, repositories, mappers, unit of work, event bus | SQLAlchemy repos, `InMemoryEventBus`, MinIO storage |
| **presentation** | HTTP routers, DTOs, dependency wiring, middleware | FastAPI routers, Pydantic DTOs, security headers |

Use cases return `Result[T, DomainError]`. Routers stay thin: they translate a
DTO into a command, call the use case, and map a `DomainError` to HTTP in a
global handler using the envelope `{error: {code, message, field}}`. HTTP status
codes are explicit (201 / 204 / 415) and validation follows the order
404 (not found) → 403 (forbidden) → 422 / 400 (bad data).

## Module layout

```
backend/app/
  main.py            # create_app(): mounts /api/v1/* routers + middleware
  config.py          # pydantic-settings configuration
  container.py       # dependency injection (per-request UoW + use cases)
  shared/            # cross-cutting building blocks
    domain/          #   Entity, AggregateRoot, ValueObject, EntityId, DomainEvent, errors
    application/     #   IRepository, IUnitOfWork, IEventBus, Result/Ok/Err, use_case base
    infrastructure/  #   DB session, in-memory event bus, structlog logging
    presentation/    #   api_response, error_handler, deps, middleware/
  modules/<m>/       # m in {identity, content, files, engagement, notifications*, audit*}
    domain/          #   aggregates, value objects, events
    application/     #   ports.py, commands.py, use_cases/
    infrastructure/  #   orm/, repositories/, mappers.py, unit_of_work.py
    presentation/    #   routers/, dto/, deps.py
  models/            # transitional ORM classes (aliased by the modules)
  maintenance/       # cleanup_orphan_files.py (runs as a CronJob)
```

`* notifications` and `audit` are skeleton modules reserved for future work.

### Modules

| Module | Responsibility |
|--------|----------------|
| **identity** | Users, roles, permissions, refresh tokens; JWT auth with rotation and reuse detection; RBAC + per-user ACL; Argon2id password hashing |
| **content** | Posts and comments (materialized-path nesting, soft delete), categories, tags, keyset pagination, full-text search (tsvector) |
| **files** | Generic file module: proxied upload + presigned fallback to MinIO, thumbnails, attachments for posts/comments, avatars, category and thread icons, orphan cleanup |
| **engagement** | Lightweight social features (raw-SQL, deliberately thin): likes (`reactions`), the `user_stats` view, category ownership |
| **notifications**, **audit** | Skeletons for future RabbitMQ-driven phases |

### Transitional ORM

`UserOrm`, `PostOrm`, `CommentOrm`, `CategoryOrm` in `app/models/` are **aliases**
of the module ORM classes — one class maps one table, so there is no double
mapping. Newer tables (`tags`, `post_tags`, `reactions`) live in their module's
`infrastructure/orm`. The transitional layer is excluded from strict lint/mypy and
will eventually be absorbed into `modules/*/infrastructure/orm`.

## Domain events

Aggregates record events with `record_event` and expose them via `pull_events`.
Events are currently dispatched through an `InMemoryEventBus`; the planned
RabbitMQ broker (see the roadmap) will let events cross process boundaries for
notifications and audit.

## Architecture Decision Records

| ID | Decision | Rationale |
|----|----------|-----------|
| ADR-1 | Modular monolith, not microservices | One DB, one process — cheapest to run; modules with clear contracts can be split out later. |
| ADR-2 | Clean Architecture (4 layers) | Hard boundary between business rules and the framework. |
| ADR-3 | RabbitMQ as the event broker (planned) | At-least-once delivery, retries, DLQ. |
| ADR-4 | PostgreSQL as the single store; Redis optional | Postgres covers UUID, JSONB, views, partial indexes. |
| ADR-5 | PyJWT + a refresh-token whitelist in `refresh_tokens` | Simple, auditable, easy to revoke all sessions. |
| ADR-6 | Argon2id for password hashing (`argon2-cffi`) | Current OWASP recommendation. |
| ADR-7 | Alembic migrations, no `create_all` | Versioned, reversible, readable schema history. |
| ADR-8 | WebSocket — simple version, single replica (planned) | Demonstrates WS without a backplane; sticky sessions in Ingress. |
| ADR-9 | Observability: Prometheus + Grafana + Loki | Structured JSON logs via `structlog` to stdout. |
| ADR-10 | HPA on the backend deployment | Shows the HTTP layer is stateless and scales horizontally. |
| ADR-11 | RBAC + ACL: role = permission bundle, optional per-user override | Lets one admin hold different permissions than another. |
| ADR-12 | Code and documentation in English | Easier to showcase the repository. |
| ADR-13 | UUID v4 public keys (`public_id`), `bigserial` internal PK | Hides sequence IDs in the API; sorting by `(created_at, public_id)`. |
| ADR-14 | MinIO (S3) + presigned URLs, metadata in DB | One generic `/api/v1/files/*` endpoint; bytes stay out of the backend. |

See also: [Database](./02-database.md) · [Security](./03-security.md) ·
[Deployment](./04-deployment.md).
