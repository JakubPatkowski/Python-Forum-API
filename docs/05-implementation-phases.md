# 05 — Fazy implementacji (roadmap dla Opus 4.6)

> **Jak korzystać:** każda faza ma cel, listę plików do utworzenia/zmiany, kryteria gotowości,
> oraz **gotowy prompt startowy** do skopiowania w nowej sesji z Opus 4.6.
>
> Fazy realizuj po kolei. Każda faza zostawia działającą aplikację (zielony Swagger, zielone testy).

---

## Faza 0 — Bootstrap: skeleton v3, Alembic, refactor struktury

**Cel.** Przygotować strukturę katalogów Clean Architecture, podłączyć Alembic, przepisać `main.py`
na app factory, dodać `shared/` z bazowymi abstrakcjami, **nic merytorycznego się nie zmienia
w API** — to czysty refactor.

### Pliki do utworzenia / zmiany

```
backend/
├── alembic/                                    [NOWE]
├── alembic.ini                                 [NOWE]
├── pyproject.toml                              [NOWE]   (ruff, mypy, pytest)
└── app/
    ├── main.py                                 [REFAKTOR — app factory]
    ├── config.py                               [POZOSTAJE]
    ├── container.py                            [NOWE]   (DI wiring)
    ├── shared/                                 [NOWE]
    │   ├── domain/
    │   │   ├── entity.py
    │   │   ├── value_object.py
    │   │   ├── entity_id.py
    │   │   ├── events.py
    │   │   └── errors.py
    │   ├── application/
    │   │   ├── repository.py
    │   │   ├── unit_of_work.py
    │   │   ├── event_bus.py
    │   │   ├── result.py
    │   │   └── use_case.py
    │   ├── infrastructure/
    │   │   ├── db/
    │   │   │   ├── base.py                     (Base + naming convention)
    │   │   │   └── session.py                  (SessionLocal, get_db)
    │   │   ├── eventbus/
    │   │   │   └── in_memory.py                (InMemoryEventBus — RabbitMQ w fazie 4)
    │   │   └── logging/
    │   │       └── setup.py                    (structlog config)
    │   └── presentation/
    │       ├── api_response.py
    │       ├── error_handler.py
    │       └── deps.py
    └── modules/                                [NOWE — puste folder per moduł]
        ├── identity/
        ├── content/
        ├── files/
        ├── notifications/
        └── audit/

# Stare pliki zostawiamy w backend/app/{models,schemas,services,routers} — będą stopniowo
# konsumowane przez moduły. NIE usuwamy ich teraz.
```

### Kryteria gotowości

- `alembic upgrade head` przechodzi (jedna pusta migracja baseline = obecny schemat z `create_all`).
- `uvicorn app.main:app` startuje, `GET /health/live` zwraca 200.
- Stare endpointy działają jak przedtem (regresja zero).
- `ruff check .` i `mypy app/` przechodzi (warningi OK, błędy NIE).

### Prompt startowy

```
Realizujemy Fazę 0 z docs/05-implementation-phases.md (Bootstrap v3).

Zadania:
1. Stwórz pyproject.toml z konfiguracją ruff (E, F, I, B), mypy (strict),
   pytest-asyncio. Wszystko po angielsku.
2. Stwórz strukturę katalogów wg sekcji "Pliki do utworzenia / zmiany" w fazie 0.
3. Zaimplementuj wszystkie abstrakcje z docs/01-clean-architecture.md sekcja 3
   (Entity, AggregateRoot, ValueObject, EntityId, DomainEvent, IRepository,
    IUnitOfWork, IEventBus, Result, ApiResponse, ErrorResponse, PaginatedResponse).
   Wszystkie typowane (PEP 695 lub TypeVar w starszym stylu).
4. Stwórz InMemoryEventBus jako pierwszą implementację IEventBus (RabbitMQ w fazie 4).
5. Stwórz structlog setup w shared/infrastructure/logging/setup.py.
6. Stwórz global error handler — DomainError→HTTP w shared/presentation/error_handler.py.
7. Stwórz baseline Alembic:
   - `alembic init alembic`
   - Skonfiguruj env.py żeby czytał URL z app.config.settings
   - Stwórz pierwszą migrację `0001_baseline.py` — pusta (--autogenerate na obecnej DB).
8. Refaktor app/main.py do "app factory": funkcja create_app() w main.py.
9. NIE zmieniaj istniejących routerów — mają działać identycznie.

Kryterium akceptacji: stare endpointy działają, alembic upgrade head OK,
ruff/mypy clean, struktura odpowiada drzewu z dokumentu.

Po zakończeniu zaktualizuj TASKS.md i memory/.
```

---

## Faza 1 — Moduł `identity` (User, Role, Permission, JWT)

**Cel.** Pełna implementacja domeny identity: encje, repozytoria, use case'y, routery `auth` i `users`.
Stare `routers/auth.py` i `routers/users.py` zostają **wyłączone** i zastąpione.

### Pliki

```
modules/identity/
├── domain/
│   ├── user.py                                 (User AggregateRoot)
│   ├── role.py                                 (Role Entity)
│   ├── permission.py                           (Permission VO, kody enum)
│   ├── refresh_token.py                        (RefreshToken Entity)
│   ├── value_objects.py                        (Email, Username, RawPassword)
│   └── events.py                               (UserRegistered, UserBlocked, ...)
├── application/
│   ├── ports.py                                (IUserRepo, IRoleRepo, ITokenService, IPasswordHasher)
│   ├── commands.py                             (RegisterUserCommand, LoginCommand, ...)
│   └── use_cases/
│       ├── register_user.py
│       ├── login.py
│       ├── refresh_session.py
│       ├── logout.py
│       ├── assign_role.py
│       └── grant_permission.py
├── infrastructure/
│   ├── orm/                                    (UserOrm, RoleOrm, RefreshTokenOrm)
│   │   ├── user_orm.py
│   │   ├── role_orm.py
│   │   ├── permission_orm.py
│   │   └── refresh_token_orm.py
│   ├── repositories/                            (SqlAlchemy impl)
│   │   ├── user_repo.py
│   │   └── refresh_token_repo.py
│   ├── auth/
│   │   ├── argon2_hasher.py                    (IPasswordHasher)
│   │   └── pyjwt_token_service.py              (ITokenService)
│   └── mappers.py                              (ORM ↔ Domain)
└── presentation/
    ├── routers/
    │   ├── auth.py                             (/api/v1/auth/*)
    │   ├── users.py                            (/api/v1/users/*)
    │   └── admin_users.py                      (/api/v1/admin/users/*)
    └── dto/
        ├── auth_dto.py                         (RegisterRequest, LoginResponse, ...)
        └── user_dto.py
```

### Migracje Alembic

- `0002_create_identity_tables.py` — users, roles, permissions, role_permissions, user_roles, user_permissions, refresh_tokens.
- `0003_seed_identity.py` — wgranie permission codes + ról `user`/`moderator`/`admin` z bundlami.

### Kryteria gotowości

- `POST /api/v1/auth/register` → 201, tworzy usera z rolą `user`.
- `POST /api/v1/auth/login` → access + refresh.
- `POST /api/v1/auth/refresh` → rotacja, stary refresh dostaje status `rotated`.
- Drugie użycie tego samego refresh → 401 + revoke wszystkich sesji + event `RefreshTokenReuseDetected`.
- `GET /api/v1/users/me` z access tokenem → dane usera.
- `PATCH /api/v1/admin/users/{id}/role` z permission `role.manage` → zmienia rolę.
- Testy jednostkowe domeny (`tests/unit/identity/`) zielone.
- Testy integracyjne `tests/integration/identity/test_auth_flow.py` zielone (testcontainers Postgres).

### Prompt startowy

```
Realizujemy Fazę 1 z docs/05-implementation-phases.md (moduł identity).

Kontekst: poprzednia faza 0 zostawiła strukturę katalogów i abstrakcje w shared/.
Stary kod w app/models, app/routers itd. dalej istnieje, ale go zignorujemy
i podmienimy na nowy moduł.

Implementuj zgodnie z docs/01-clean-architecture.md (sekcja 4.1 identity) oraz
docs/03-security.md. Strict TDD nie wymagane, ale każdy use case ma testy
unit + integration test pełnego flow auth.

Zadania:
1. Domain layer w modules/identity/domain/:
   - User AggregateRoot z metodami: register(), change_password(), block(),
     unblock(), assign_role(), revoke_role(), grant_permission(), revoke_permission().
     User publikuje DomainEventy.
   - Email, Username, RawPassword jako Value Objects z walidacją.
   - Role Entity, Permission VO.
   - RefreshToken Entity z metodami rotate_to(), revoke().
2. Application layer w modules/identity/application/:
   - Porty IUserRepository, IRefreshTokenRepository, IPasswordHasher, ITokenService.
   - Use case'y wg listy z fazy. Każdy zwraca Result[T, E].
3. Infrastructure layer:
   - SQLAlchemy ORM dla wszystkich encji (declarative_base z shared/).
   - Repozytoria implementujące porty.
   - Mappery ORM↔Domain.
   - Argon2Hasher z argon2-cffi.
   - PyJWTTokenService z PyJWT, używający settings.SECRET_KEY.
4. Presentation layer:
   - Routery /api/v1/auth/* i /api/v1/users/*.
   - Pydantic DTO.
   - Dependency get_current_user, requires(*permission_codes).
5. Migracje Alembic 0002 i 0003 (CREATE tables + seed).
6. Refresh token rotation z reuse detection wg docs/03-security.md sekcja 2.3.
7. Testy:
   - unit/ — testy domeny User (register/block/grant), VO Email walidacja.
   - integration/ — testy flow login→refresh→refresh→reuse_detected→revoke_all.
8. W app/main.py podmień stary include_router(auth, users) na nowe.
   Stary kod w app/routers/auth.py, users.py — usuń (już niepotrzebny).

Kryterium akceptacji: lista z sekcji "Kryteria gotowości" fazy 1. Testy zielone.

Po zakończeniu update TASKS.md i memory/.
```

---

## Faza 2 — Moduł `content` (Post, Comment, Tag, Category)

**Cel.** Migracja content do nowej architektury z prawidłowym drzewem komentarzy
(materialized path).

### Pliki — analogiczna struktura

```
modules/content/
├── domain/
│   ├── post.py
│   ├── comment.py                              (z materialized path)
│   ├── category.py
│   ├── tag.py
│   ├── value_objects.py                        (Slug, MarkdownContent)
│   └── events.py
├── application/
│   ├── ports.py
│   ├── commands.py
│   ├── queries.py                              (list_posts, get_comment_tree)
│   └── use_cases/
│       ├── create_post.py
│       ├── update_post.py
│       ├── delete_post.py
│       ├── add_comment.py                      (z walidacją głębokości i obliczeniem path)
│       ├── update_comment.py
│       ├── delete_comment.py                   (soft delete)
│       ├── manage_category.py
│       └── manage_tag.py
├── infrastructure/
│   ├── orm/
│   ├── repositories/
│   └── mappers.py
└── presentation/
    ├── routers/
    │   ├── posts.py
    │   ├── comments.py
    │   ├── categories.py
    │   └── tags.py
    └── dto/
```

### Migracje

- `0004_create_content_tables.py` — categories, tags, posts, post_tags, comments + indeksy.
- `0005_seed_default_categories.py` — opcjonalnie kilka kategorii startowych.

### Kryteria gotowości

- `POST /api/v1/posts` z markdown i tagami → 201 + post w DB + event `PostCreated`.
- `POST /api/v1/comments` z `parent_id=null` → komentarz top-level, `depth=0`, `path='00000XXX'`.
- `POST /api/v1/comments` z `parent_id=X` → `depth=parent.depth+1`, `path=parent.path + '.' + own_id`.
- `GET /api/v1/posts/{id}/comments?tree=true` → drzewo w kolejności DFS (sort by `path`).
- `DELETE /api/v1/comments/{id}` → soft delete (`is_deleted=true`, content="[deleted]"), children zostają.
- Walidacja `MAX_COMMENT_DEPTH` (configurable, domyślnie 5).
- Keyset pagination `GET /api/v1/posts?cursor=...&limit=20`.

### Prompt startowy

```
Realizujemy Fazę 2 z docs/05-implementation-phases.md (moduł content).

Kontekst: Fazy 0 i 1 zakończone. identity działa, mamy User i permissions z JWT.

Zadania:
1. Domain: Post, Comment, Category, Tag — wszystkie AggregateRoot / Entity.
   Comment ma metodę add_reply(parent) która oblicza depth i path zgodnie z
   docs/02-database-schema.md sekcja 3. Walidacja MAX_COMMENT_DEPTH w domenie.
2. Application: porty + use case'y wg listy z fazy.
   create_post.py wymaga permission "post.create".
   delete_post.py wymaga "post.delete.own" (jeśli autor) lub "post.delete.any".
   Sprawdzenie ownership w use case, nie w dependency.
3. Infrastructure: ORM + repozytoria + mappery.
4. Presentation: routery /api/v1/{posts,comments,categories,tags}.
   Keyset pagination dla listy postów.
5. Migracje 0004 (tabele content) i 0005 (kilka kategorii startowych: "Spinning",
   "Karpiowanie", "Muszka", "Sprzęt", "Łowiska").
6. Testy:
   - unit/content/test_comment_path.py (logika depth/path).
   - integration/content/test_post_flow.py.
   - integration/content/test_comment_tree.py — fixture z drzewem 4-poziomowym,
     sprawdzenie listingu DFS.
7. Podmień stare routery posts, comments, categories w app/main.py.

Kryterium akceptacji: sekcja "Kryteria gotowości" fazy 2.

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 3 — Moduł `files` (generyczny upload)

**Cel.** Jeden zestaw endpointów dla wszystkich plików (avatary, embed, załączniki).

### Pliki

```
modules/files/
├── domain/
│   ├── file.py
│   ├── value_objects.py                        (StorageKey, FileSha256, MimeType)
│   └── events.py
├── application/
│   ├── ports.py                                (IFileRepository, IFileStorage)
│   ├── commands.py
│   └── use_cases/
│       ├── upload_file.py
│       ├── download_file.py
│       └── delete_file.py
├── infrastructure/
│   ├── orm/
│   ├── repositories/
│   ├── storage/
│   │   └── local_disk.py                        (IFileStorage impl)
│   └── mappers.py
└── presentation/
    ├── routers/files.py                         (/api/v1/files/*)
    └── dto/
```

### Migracje

- `0006_create_files_table.py` — tabela `files` z polimorficznym ownership wg docs/02 sekcja 4.

### Kryteria gotowości

- `POST /api/v1/files?owner_type=post&owner_id=UUID` (multipart) → 201 + metadata.
- `POST /api/v1/files?owner_type=user_avatar` → upload, owner_user_id = current user, ustawia
  `users.avatar_file_id`.
- `GET /api/v1/files/{file_id}` → pobranie pliku (streaming).
- `DELETE /api/v1/files/{file_id}` — uploader lub `file.delete.any`.
- Walidacja MIME (python-magic), max size 10 MiB, generowanie storage_key z UUID.
- Avatar usera → po zmianie odpinamy stary plik (event `FileDeleted`).

### Prompt startowy

```
Realizujemy Fazę 3 z docs/05-implementation-phases.md (moduł files).

Kontekst: Fazy 0-2 zakończone. identity i content działają.

Zadania:
1. Domain File AggregateRoot z metodami attach_to_post(), attach_to_comment(),
   attach_to_user_avatar(), detach().
2. Application ports + use case'y upload/download/delete.
   upload_file.py używa python-magic do MIME sniffing.
3. Infrastructure: LocalDiskStorage zapisujący do settings.UPLOAD_DIR
   (w k8s PVC). Streaming read/write żeby nie ładować pliku do RAM.
4. Presentation: jeden generyczny endpoint /api/v1/files z parametrami query
   owner_type i owner_id. Plus GET /api/v1/files/{id}, /info, DELETE.
5. Aktualizacja identity:
   - User.set_avatar(file_id) z eventem AvatarChanged.
   - Endpoint POST /api/v1/users/me/avatar wewnątrz identity wywołuje upload + set_avatar.
6. Aktualizacja content:
   - Endpointy POST /api/v1/posts/{post_id}/files, /api/v1/comments/{comment_id}/files
     są syntactic sugar nad /api/v1/files?owner_type=...&owner_id=... — implementacja
     przez delegację, nie duplikacja logiki.
   - W treści markdown wspieramy embed file:UUID.
7. Migracja 0006.
8. Usuń stary moduł attachments i jego endpointy (DEAD CODE).
9. Testy:
   - unit/files/test_file_domain.py.
   - integration/files/test_upload_flow.py — multipart upload, weryfikacja sha256,
     download, MIME sniffing.

Kryterium akceptacji: jednym endpointem obsługujemy avatar, post attachment,
comment attachment. Lista z "Kryteria gotowości".

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 4 — Event Bus na RabbitMQ + moduły `notifications` i `audit`

**Cel.** Przejście z InMemoryEventBus na RabbitMQ, dodanie konsumentów.

### Pliki

```
shared/infrastructure/eventbus/
├── rabbitmq.py                                 [NOWE]  (RabbitMQEventBus z aio-pika)
└── outbox.py                                   [OPCJONALNE]  (Outbox pattern impl)

modules/notifications/
├── domain/notification.py
├── application/handlers/
│   ├── on_post_created.py                       (kreuje Notification dla followersów)
│   ├── on_comment_added.py                      (Notification dla autora postu)
│   └── on_user_blocked.py
├── infrastructure/orm/
└── presentation/                               (rest endpoints + WS w fazie 5)

modules/audit/
├── domain/audit_entry.py
├── application/handlers/
│   └── audit_all_events.py                      (subscribes "#")
├── infrastructure/orm/
└── presentation/routers/admin_audit.py          (GET /api/v1/admin/audit)

backend/
├── worker.py                                   [NOWE]  (osobny entrypoint dla konsumentów)
└── Dockerfile                                  [REFACTOR — opcjonalne osobne worker image]
```

### Migracje

- `0007_create_notifications.py`
- `0008_create_audit_log.py`

### K8s

```yaml
# k8s/backend/worker-deployment.yaml — NOWE
# Osobny Deployment uruchamia consumer'y z RabbitMQ.
# Możemy mieć replicas: 2 — RabbitMQ rozdzieli wiadomości round-robin.
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: worker
          image: forum-wedkarskie-backend:latest
          command: ["python", "-m", "app.worker"]
```

### Kryteria gotowości

- `POST /api/v1/posts` → event `content.PostCreated` ląduje w RabbitMQ.
- Worker `audit` zapisuje wpis w `audit_log`.
- Worker `notifications` tworzy `Notification` dla followersów (na razie: bez follower system,
  tworzymy notyfikację dla admina — pokaz mechanizmu).
- `GET /api/v1/admin/audit` zwraca wpisy audytu (paginacja).
- DLQ działa: ręcznie podrzucony niepoprawny komunikat → ląduje w `forum.events.dlx`.

### Prompt startowy

```
Realizujemy Fazę 4 z docs/05-implementation-phases.md (RabbitMQ event bus + moduły
notifications i audit).

Kontekst: Fazy 0-3 zakończone. Mamy InMemoryEventBus, eventy są publikowane ale tracone.

Zadania:
1. RabbitMQEventBus w shared/infrastructure/eventbus/rabbitmq.py wg
   docs/04-infrastructure.md sekcja 7. aio-pika, exchange forum.events (topic),
   DLX forum.events.dlx, kolejki per moduł.
2. Konfiguracja: RABBITMQ_URL w settings, deploy RabbitMQ w k8s.
3. Wymień InMemoryEventBus na RabbitMQEventBus w DI container.
   Dla testów: InMemoryEventBus dalej dostępny.
4. Moduł audit:
   - AuditEntry domain entity.
   - Handler subskrybuje "#" (wszystkie eventy), zapisuje do audit_log.
   - Endpoint GET /api/v1/admin/audit (permission audit.read).
5. Moduł notifications:
   - Notification entity (id, user_id, type, payload, read_at, created_at).
   - Handlery: on_post_created, on_comment_added.
   - Endpointy: GET /api/v1/notifications (mine), POST /api/v1/notifications/{id}/read.
6. Worker entrypoint:
   - backend/app/worker.py: starts consumers (audit + notifications).
   - W deployment k8s osobny pod `backend-worker` (replicas: 2).
7. Migracje 0007, 0008.
8. Testy:
   - integration/eventbus/test_publish_consume.py z RabbitMQ container (testcontainers).
   - integration/audit/test_audit_log.py.
   - integration/notifications/test_post_creates_notification.py.

Kryterium akceptacji: po utworzeniu posta przez API, w audit_log pojawia się wpis,
w notifications nowy rekord. RabbitMQ management UI pokazuje exchange + queues.

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 5 — WebSocket (prosta wersja)

**Cel.** Live notyfikacje dla zalogowanego usera. Sticky sessions w Ingress.

### Pliki

```
modules/notifications/presentation/ws/
├── connection_manager.py                       (in-memory dict[user_id -> set[ws]])
└── notifications.py                            (endpoint /ws/notifications)

shared/presentation/deps.py
└── get_current_user_ws                         (auth dla WS — token w query lub pierwszy msg)
```

### k8s

`k8s/ingress.yaml` już zawiera sticky cookie. W tej fazie tylko aplikujemy zmianę.

### Kryteria gotowości

- Klient łączy się `wss://forum.local/ws/notifications?token=...`.
- Po stworzeniu komentarza przez API X → autor posta (jeśli ma otwarty WS) dostaje JSON push.
- Disconnect / reconnect działa.
- Heartbeat (klient wysyła `ping` co 30s, serwer ignoruje — wystarczy że TCP keepalive trzyma).

### Prompt startowy

```
Realizujemy Fazę 5 z docs/05-implementation-phases.md (WebSocket prosta wersja).

Kontekst: Fazy 0-4 zakończone. Notifications module działa, ale tylko REST polling.

Zadania:
1. ConnectionManager wg docs/04-infrastructure.md sekcja 8.
   Globalny singleton per replika.
2. Endpoint /ws/notifications:
   - Autoryzacja: ?token=ACCESS_JWT albo header (FastAPI WS wspiera oba).
   - Rejestracja w manager po WebSocket.accept().
   - Loop with try/except WebSocketDisconnect.
3. Handler on_notification_created w module notifications:
   - Po stworzeniu Notification w DB, broadcastuj do ws_manager.broadcast_to(user_id).
   - UWAGA: handler działa w **kontekście workera** (consumer RabbitMQ).
     Worker NIE trzyma WS — WS są w pod backendu. ROZWIĄZANIE:
     - notification handler PUBLIKUJE event "notifications.NotificationCreated" do RabbitMQ.
     - Backend pods subskrybują ten event na lokalnym handlerze i broadcastują do swojego ws_manager.
     - Każdy pod backendu ma osobną queue (np. notifications.ws.<podname>), bindowane do
       routing_key "notifications.NotificationCreated".
     - Ekskluzywne queues z autoDelete: queue żyje tylko dla danego poda.
   - W "prostej wersji" — jeśli zbyt skomplikowane: zostawiamy in-process (notification handler
     jednocześnie zapisuje do DB i broadcastuje lokalnie). Działa tylko gdy worker i backend
     to ten sam pod / proces. Akceptowalne dla MVP.
4. Ingress sticky cookie — zaaplikuj k8s/ingress.yaml.
5. Frontend (minimal): hook useWebSocket(token), nasłuchiwanie message,
   wyświetlenie toasta. Implementacja po stronie frontu — osobne zadanie, ale
   pokaż prosty kod do skopiowania.
6. Testy:
   - integration/notifications/test_ws_broadcast.py — connect, trigger event, expect message.

Kryterium akceptacji: zalogowany user widzi notyfikację o nowym komentarzu pod swoim postem
w czasie rzeczywistym (gdy spięty z replikę gdzie powstał event — to wybrany trade-off).

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 6 — Widoki DB + FTS + keyset pagination

**Cel.** Performance: widoki SQL dla list, full-text search, keyset pagination zamiast `OFFSET`.

### Pliki

- `0009_create_views.py` — wszystkie widoki z docs/02 sekcja 6.
- `0010_add_tsvector_to_posts.py` (jeśli nie zrobione w fazie 2).
- `modules/content/infrastructure/repositories/post_repo.py` — używa `v_posts_with_stats`.
- `modules/content/infrastructure/repositories/comment_repo.py` — używa `v_comment_tree_lite`.
- `modules/content/application/use_cases/search_posts.py` — używa `to_tsquery`.

### Kryteria gotowości

- `GET /api/v1/posts?cursor=eyJ...` — keyset pagination (cursor = base64({created_at, id})).
- `GET /api/v1/posts/search?q=lipień` — FTS.
- `GET /api/v1/posts/{id}/comments?tree=true` — wykorzystuje widok, jeden SELECT.
- Plan EXPLAIN dla listingu nie używa `Seq Scan` na `posts`.

### Prompt startowy

```
Realizujemy Fazę 6 z docs/05-implementation-phases.md (widoki DB + FTS + keyset pagination).

Zadania:
1. Migracja 0009 — wszystkie widoki z docs/02-database-schema.md sekcja 6.
2. Repozytoria content:
   - PostRepository.list_with_stats(cursor, limit, category=None) zwraca z v_posts_with_stats.
   - CommentRepository.tree_for_post(post_id) zwraca z v_comment_tree_lite ORDER BY path.
3. Keyset pagination helper w shared/application/pagination.py:
   - encode_cursor({"created_at": ..., "id": ...}) -> str
   - decode_cursor(str) -> dict
   - WHERE (created_at, id) < (cursor.created_at, cursor.id) ORDER BY created_at DESC, id DESC.
4. SearchPostsUseCase z to_tsquery('simple', :query).
5. Endpoint GET /api/v1/posts/search?q=... z keyset pagination.
6. Testy:
   - integration/content/test_keyset_pagination.py.
   - integration/content/test_search.py.
7. Dokument docs/02 sekcja 6 — uaktualnić jeśli widok się różni.

Kryterium akceptacji: lista 1000 fake postów, paginacja 20-na-strone bez Seq Scan
(EXPLAIN ANALYZE w teście).

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 7 — Observability (Prometheus + Grafana, structlog)

**Cel.** Aplikacja ma `/metrics`, structured logging, dashboardy.

### Pliki

```
shared/infrastructure/metrics.py                 (Prometheus counters/histograms)
shared/presentation/middleware/request_logging.py
shared/presentation/middleware/security_headers.py

k8s/monitoring/
├── prometheus-values.yaml
├── servicemonitor-backend.yaml
└── dashboards/forum-overview.json
```

### Kryteria gotowości

- `kubectl port-forward svc/kube-prometheus-grafana 3000:80 -n monitoring` → dashboard "Forum Overview".
- `GET /metrics` zwraca metryki Prometheus.
- Każdy request loggowany jako JSON z `request_id`.
- Custom counter `forum_posts_created_total` rośnie po `POST /api/v1/posts`.

### Prompt startowy

```
Realizujemy Fazę 7 z docs/05-implementation-phases.md (Observability).

Zadania:
1. Setup structlog wg docs/04 sekcja 9.5 (jeśli nie z fazy 0 — uzupełnij).
2. Middleware request_logging.py: X-Request-ID, structlog contextvars, log każdy request.
3. Middleware security_headers.py wg docs/03 sekcja 5.
4. prometheus-fastapi-instrumentator instrumentuje aplikację → /metrics.
5. Custom metryki w shared/infrastructure/metrics.py:
   - Counter posts_created, comments_created, login_failures, events_published.
   - Histogram use_case_duration z label "use_case".
6. Decorator @timed("use_case_name") dla use case'ów.
7. Helm install kube-prometheus-stack do monitoring namespace.
8. k8s/monitoring/servicemonitor-backend.yaml — scrape /metrics z backendu.
9. Grafana dashboard JSON: forum-overview.json z panelami:
   - HTTP request rate, error rate, p95 latency
   - Domain activity (posts/s, comments/s, signups/s)
   - HPA replicas current
   - RabbitMQ queue depths (jeśli mamy rabbitmq-exporter)
10. README w k8s/monitoring/ z instrukcją deployu.

Kryterium akceptacji: kubectl port-forward Grafana, login admin/changeme,
dashboard "Forum Overview" pokazuje aktualne metryki.

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 8 — K8s polish (NetworkPolicy, HPA, cleanup CronJob)

**Cel.** Profesjonalne k8s manifests.

### Pliki

```
k8s/backend/networkpolicy.yaml
k8s/postgres/networkpolicy.yaml
k8s/rabbitmq/networkpolicy.yaml
k8s/backend/cleanup-cronjob.yaml             (DELETE expired refresh tokens)
k8s/backend/poddisruptionbudget.yaml         (minAvailable: 1)
```

### Kryteria gotowości

- `kubectl apply -f k8s/` idempotent, brak błędów.
- `kubectl describe networkpolicy` pokazuje ograniczenia.
- CronJob `cleanup-refresh-tokens` widoczny, action wewnątrz: `alembic ... ` lub `python -m app.maintenance.cleanup_tokens`.
- PDB nie pozwala na rolling update które wyłącza wszystkie repliki naraz.

### Prompt startowy

```
Realizujemy Fazę 8 z docs/05-implementation-phases.md (k8s polish).

Zadania:
1. NetworkPolicy dla backend (egress: postgres, rabbitmq, DNS).
2. NetworkPolicy dla postgres (ingress tylko z app=backend i app=pgadmin).
3. NetworkPolicy dla rabbitmq (ingress tylko z app=backend i app=worker).
4. CronJob cleanup-refresh-tokens (@daily):
   - Image: forum-wedkarskie-backend.
   - Command: python -m app.maintenance.cleanup_refresh_tokens.
   - Implementuj moduł cleanup w app/maintenance/.
5. PodDisruptionBudget dla backend: minAvailable: 1.
6. Refactor scripts/deploy.sh — kolejność apply, czekanie na PVC bound.

Kryterium akceptacji: minikube z włączonym networking addon: backend ma dostęp tylko
do tego co policy pozwala. CronJob raz dziennie czyści tokeny.

Po zakończeniu update TASKS.md, memory/.
```

---

## Faza 9 — CI/CD + testy E2E

**Cel.** GitHub Actions: lint, test, build images.

### Pliki

```
.github/workflows/
├── ci.yml                                       (lint, mypy, pytest)
├── build-images.yml                             (docker build + push to ghcr.io na tagi)
└── deploy.yml                                   (opcjonalnie — manualny trigger do staging)

tests/e2e/
└── test_full_user_flow.py                       (register → login → create post → comment → notification)
```

### Kryteria gotowości

- Push do `main` → workflow `ci.yml` zielony (ruff + mypy + pytest).
- Tag `v*` → build images i push do ghcr.io.
- README ma badge'a CI.

### Prompt startowy

```
Realizujemy Fazę 9 z docs/05-implementation-phases.md (CI/CD + E2E).

Zadania:
1. .github/workflows/ci.yml:
   - matrix: python 3.12
   - cache pip
   - ruff check, mypy app/, pytest -m "not integration" (lub z testcontainers usługą)
2. .github/workflows/build-images.yml on tag v*:
   - docker buildx, push to ghcr.io/<owner>/forum-wedkarskie-{backend,frontend}:VERSION
3. tests/e2e/test_full_user_flow.py:
   - testcontainers Postgres + RabbitMQ
   - httpx.AsyncClient na app=create_app()
   - flow: register → login → me → create category (jako admin) →
     create post → add comment → list comments → upload avatar
4. README.md update — badge CI, instrukcja "make dev", "make deploy".
5. Makefile z targetami: dev, test, lint, format, deploy, undeploy.

Kryterium akceptacji: zielony CI badge w README, lokalnie `make test` przechodzi.

Po zakończeniu update TASKS.md, memory/.
```

---

## Podsumowanie kolejności

| #  | Faza                                              | Ryzyko / blocking          | Dependency  |
|----|---------------------------------------------------|----------------------------|-------------|
| 0  | Bootstrap (Alembic, shared/, struktura)           | Niskie                     | —           |
| 1  | identity (User, Role, Permission, JWT)                 | Średnie — auth jest krytyczne | 0       |
| 2  | content (Post, Comment, Tag, Category)            | Średnie                    | 0, 1        |
| 3  | files (generyczny upload)                          | Niskie                     | 0, 1, 2     |
| 4  | RabbitMQ event bus + notifications + audit        | Wysokie — najbardziej ambitne | 0-3      |
| 5  | WebSocket prosta wersja                            | Niskie                     | 4           |
| 6  | DB views + FTS + keyset pagination                 | Niskie                     | 2           |
| 7  | Observability (Prometheus + Grafana)               | Niskie                     | 0           |
| 8  | k8s polish (NetworkPolicy, CronJob, PDB)           | Niskie                     | wszystko    |
| 9  | CI/CD + E2E                                        | Niskie                     | wszystko    |

**Możliwa optymalizacja czasowa:** fazy 6, 7, 8, 9 są w dużej mierze niezależne — można robić
równolegle lub przeplatać.

**Faza wartościowa do obrony** w kolejności znaczenia: 1, 2, 4, 7, 8.
Jeśli brakuje czasu — minimum to fazy 0-4 + 7 (event-driven + observability robi największe wrażenie).
