# Tasks

> Plan v3 (Clean Architecture, modular monolith). Pełne szczegóły każdej fazy:
> `docs/05-implementation-phases.md`. Każda faza ma gotowy prompt dla Opus 4.6.

## v3 — Roadmap (kolejność)

### Faza 0 — Bootstrap

- [x] (v3-F0) Stwórz `backend/pyproject.toml` (ruff, mypy strict, pytest-asyncio)
- [x] (v3-F0) Stwórz strukturę `backend/app/{shared,modules}/` wg `docs/01-clean-architecture.md` sekcja 2
- [x] (v3-F0) Zaimplementuj bazowe abstrakcje w `shared/`: Entity, AggregateRoot, ValueObject, EntityId, DomainEvent, IRepository, IUnitOfWork, IEventBus, Result, ApiResponse, ErrorResponse
- [x] (v3-F0) `InMemoryEventBus` jako pierwszy IEventBus (RabbitMQ w F4)
- [x] (v3-F0) `structlog` setup w `shared/infrastructure/logging/`
- [x] (v3-F0) Global error handler `DomainError → HTTP` w `shared/presentation/`
- [x] (v3-F0) Alembic init + `env.py` czyta URL z settings + baseline migration `0001_baseline.py`
- [x] (v3-F0) Refactor `app/main.py` → app factory `create_app()`
- [ ] (v3-F0) `ruff check .` i `mypy app/` clean — uruchomić lokalnie po `uv sync` (w sandboxie zweryfikowano tylko `py_compile`)
- [x] (v3-F0) **DODANO**: uv jako package manager (`pyproject.toml` + `uv.lock`), Dockerfile multi-stage z `ghcr.io/astral-sh/uv`, docker-compose ze `backend_venv` volume
- [x] (v3-F0) **DODANO**: `k8s/backend/migration-job.yaml` — Job `alembic upgrade head` zamiast init container
- [x] (v3-F0) **DODANO**: zmiana nazwy modułu auth/users z `iam` na `identity` (w docs, memory, TASKS, strukturze katalogów)

### Faza 1 — Moduł identity (auth + RBAC + ACL)

- [ ] (v3-F1) Domain: `User` AR z metodami register/block/assign_role/grant_permission, `Email`/`Username` VO, `Role`, `Permission`, `RefreshToken`
- [ ] (v3-F1) Application: porty + use case'y `register/login/refresh/logout/assign_role/grant_permission`
- [ ] (v3-F1) Infrastructure: SQLAlchemy ORM, repozytoria, mappery, `Argon2Hasher`, `PyJWTTokenService`
- [ ] (v3-F1) Presentation: routery `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/admin/users/*`
- [ ] (v3-F1) Migracje `0002_create_identity_tables.py`, `0003_seed_identity.py` (permissions + role bundles)
- [ ] (v3-F1) Refresh token rotation + reuse detection (wg `docs/03-security.md` 2.3)
- [ ] (v3-F1) Testy unit (domena) + integration (auth flow z testcontainers Postgres)
- [ ] (v3-F1) Usuń stare `routers/auth.py`, `routers/users.py`

### Faza 2 — Moduł content (posts + comments z materialized path)

- [ ] (v3-F2) Domain: `Post`, `Comment` (z `depth` + `path`), `Category`, `Tag`
- [ ] (v3-F2) Walidacja `MAX_COMMENT_DEPTH` w domenie
- [ ] (v3-F2) Application: porty + use case'y create/update/delete post & comment, manage_category/tag
- [ ] (v3-F2) Infrastructure: ORM, repozytoria, mappery
- [ ] (v3-F2) Presentation: routery `/api/v1/posts`, `/api/v1/comments`, `/api/v1/categories`, `/api/v1/tags`
- [ ] (v3-F2) Migracje `0004_create_content_tables.py`, `0005_seed_categories.py`
- [ ] (v3-F2) Soft delete dla komentarzy
- [ ] (v3-F2) Testy: depth/path logic, listing drzewa DFS po `ORDER BY path`

### Faza 3 — Moduł files (generyczny upload)

- [ ] (v3-F3) Domain: `File` AR, VO `StorageKey`/`Sha256`/`MimeType`
- [ ] (v3-F3) Application: porty (`IFileRepository`, `IFileStorage`), use case'y upload/download/delete
- [ ] (v3-F3) Infrastructure: `LocalDiskStorage` streaming + MIME sniffing (`python-magic`)
- [ ] (v3-F3) Presentation: jeden generyczny endpoint `/api/v1/files?owner_type=...&owner_id=...`
- [ ] (v3-F3) Integracja: `POST /api/v1/users/me/avatar`, embed `file:UUID` w markdown
- [ ] (v3-F3) Migracja `0006_create_files_table.py` (XOR ownership)
- [ ] (v3-F3) Usuń stary moduł attachments
- [ ] (v3-F3) Testy: upload flow, sha256, MIME walidacja

### Faza 4 — RabbitMQ event bus + notifications + audit

- [ ] (v3-F4) `RabbitMQEventBus` z `aio-pika` (`docs/04-infrastructure.md` 7)
- [ ] (v3-F4) Wymień `InMemoryEventBus` na RabbitMQ w DI
- [ ] (v3-F4) Moduł `audit`: handler `#` (wszystko) → zapis do `audit_log`
- [ ] (v3-F4) Moduł `notifications`: handlery `on_post_created`, `on_comment_added` → tworzą Notification
- [ ] (v3-F4) Endpoint `GET /api/v1/admin/audit` + `GET /api/v1/notifications`
- [ ] (v3-F4) Migracje `0007_create_notifications.py`, `0008_create_audit_log.py`
- [ ] (v3-F4) Osobny entrypoint `app/worker.py` + Deployment `backend-worker` w k8s
- [ ] (v3-F4) Deploy RabbitMQ w k8s + `k8s/rabbitmq/`
- [ ] (v3-F4) Testy integracyjne z RabbitMQ container (testcontainers)

### Faza 5 — WebSocket (prosta wersja)

- [ ] (v3-F5) `ConnectionManager` (in-memory dict[user_id → set[ws]])
- [ ] (v3-F5) Endpoint `/ws/notifications` + auth z access tokena
- [ ] (v3-F5) Broadcast po stworzeniu `Notification` (w obrębie repliki)
- [ ] (v3-F5) Sticky cookie w Ingress (`nginx.ingress.kubernetes.io/affinity: cookie`)
- [ ] (v3-F5) Frontend: hook `useWebSocket(token)` + toast
- [ ] (v3-F5) Testy WS broadcast

### Faza 6 — Widoki DB + FTS + keyset pagination

- [ ] (v3-F6) Migracja `0009_create_views.py` (`v_user_effective_permissions`, `v_posts_with_stats`, `v_comment_tree_lite`, `v_top_posters_30d`)
- [ ] (v3-F6) Repozytoria content używają widoków
- [ ] (v3-F6) Keyset pagination helper (`encode_cursor`/`decode_cursor`)
- [ ] (v3-F6) `SearchPostsUseCase` z `to_tsquery`
- [ ] (v3-F6) Endpoint `GET /api/v1/posts/search?q=...`
- [ ] (v3-F6) Testy: pagination, search, EXPLAIN bez Seq Scan

### Faza 7 — Observability

- [ ] (v3-F7) Middleware request logging z `X-Request-ID`
- [ ] (v3-F7) Middleware security headers (HSTS, X-Frame-Options, ...)
- [ ] (v3-F7) `prometheus-fastapi-instrumentator` → `/metrics`
- [ ] (v3-F7) Custom counters (posts_created, comments_created, login_failures, events_published)
- [ ] (v3-F7) Helm install `kube-prometheus-stack` w namespace `monitoring`
- [ ] (v3-F7) `ServiceMonitor` dla backendu + Grafana dashboard JSON `forum-overview.json`

### Faza 8 — K8s polish

- [ ] (v3-F8) NetworkPolicy backend (egress: postgres, rabbitmq, DNS)
- [ ] (v3-F8) NetworkPolicy postgres / rabbitmq (ingress restricted)
- [ ] (v3-F8) CronJob `cleanup-refresh-tokens` (@daily)
- [ ] (v3-F8) PodDisruptionBudget backend (`minAvailable: 1`)
- [ ] (v3-F8) Refactor `scripts/deploy.sh`

### Faza 9 — CI/CD + E2E

- [ ] (v3-F9) `.github/workflows/ci.yml` (ruff + mypy + pytest)
- [ ] (v3-F9) `.github/workflows/build-images.yml` na tagi v*
- [ ] (v3-F9) `tests/e2e/test_full_user_flow.py` (testcontainers + httpx)
- [ ] (v3-F9) README z badge CI, instrukcją `make dev`/`make deploy`
- [ ] (v3-F9) Makefile

## In Progress (v0.2 — legacy, nadal aktualne do testów)

- [ ] (v0.2) Przetestować zaimplementowane endpointy v2 lokalnie (uploady + drzewo komentarzy + role)
- [ ] (v0.2) Wygenerować `pnpm-lock.yaml` (`cd frontend && corepack enable && pnpm install`)

## Todo (v0.2 — będzie wchłonięte przez fazy v3)

- [ ] Zaktualizować frontend React: stronę z drzewem komentarzy, formularz uploadu plików, render markdown
- [ ] Po zmianach modeli: wykasować PVC postgres i przedeployować (→ zastąpione przez Alembic w v3-F0)
- [ ] Zbudować obrazy w minikube i `kubectl apply -f k8s/`
- [ ] Strony frontendowe: lista postów, post, logowanie, rejestracja, profil

## Done

- [x] Stworzyć strukturę katalogów projektu (backend/, frontend/, k8s/)
- [x] Zaimplementować podstawowe endpointy FastAPI (auth, users, posts, comments, categories)
- [x] Skonfigurować Docker i docker-compose
- [x] Naprawić błąd budowania frontendu (Vite — index.html musi być w root projektu)
- [x] (v0.2) Refaktor architektury: warstwa core/, services/, podział odpowiedzialności
- [x] (v0.2) System ról RBAC: enum UserRole + require_admin/require_moderator/require_user
- [x] (v0.2) Zagnieżdżone komentarze: parent_id, depth, MAX_COMMENT_DEPTH=5, drzewo
- [x] (v0.2) Załączniki: model Attachment, storage_service, attachments router (POST/GET/DELETE)
- [x] (v0.2) Format treści: pole content_format (PLAIN/MARKDOWN) w postach i komentarzach
- [x] (v0.2) Panel administratora: Jinja2 SSR, login na cookie, dashboard + zarządzanie
- [x] (v0.2) K8s: PVC dla uploadów (uploads-pvc.yaml) + mount w backend deployment + resources
- [x] (v0.2) Frontend: pnpm zamiast npm (corepack), packageManager w package.json
- [x] (v0.2) Dodać markdown-it + dompurify do frontend dependencies
- [x] (v3-plan) Plan architektoniczny v3: ADR, schemat DB, security, infrastruktura, fazy 0-9 w `docs/`
