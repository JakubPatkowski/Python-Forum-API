# 07 — Audyt projektu i szczegółowe instrukcje dalszej implementacji

> **Autor audytu:** Opus 4.8, 2026-05-29.
> **Cel dokumentu.** (1) Rzetelny stan projektu na dziś — co zrobione, co nie. (2) Lista wykrytych
> błędów i niespójności wraz z poprawkami. (3) Skorygowana, maksymalnie szczegółowa roadmapa
> faz 3–9 + brakujący track frontendu — tak, żeby w kolejnych sesjach wystarczyło wskazać fazę.
> Ten dokument **nadpisuje** nieaktualne fragmenty `docs/05-implementation-phases.md`
> i `docs/ARCHITECTURE_PLAN.md` (różnice wypunktowane w sekcji 4).

---

## 1. Stan na 2026-05-29 (wersja kodu: 0.3.0)

Projekt jest w połowie migracji v0.2 (warstwowy) → v3 (modular monolith, Clean Architecture).
W repo współistnieją **dwie warstwy**: nowa (`app/modules/*`, `app/shared/*`) i legacy
(`app/{core,models,routers,services,schemas}`). `main.py` montuje nowe `/api/v1/*` oraz dwa
legacy routery (`attachments`, `admin` SSR).

### Co jest GOTOWE

| Faza | Zakres | Status |
|------|--------|--------|
| **0 — Bootstrap** | uv + `pyproject.toml` (ruff, mypy strict, pytest-asyncio), `shared/` (Entity, AggregateRoot, ValueObject, EntityId, DomainEvent, IRepository, IUnitOfWork, IEventBus, `Result`/`Ok`/`Err`, ApiResponse, error handler, structlog), `InMemoryEventBus`, Alembic (`env.py` czyta URL z settings, baseline `0001`), `create_app()` factory, Dockerfile multi-stage z `uv`, docker-compose, `migration-job.yaml`. | ✅ |
| **1 — identity** | Domain: `User` AR (register/block/assign_role/grant_permission/deny_permission…), VO `Email`/`Username`/`RawPassword`, `Role`, `Permission`, `RefreshToken`. Application: porty (Protocols), commands, use case'y register/login/refresh/logout/logout_all/assign_role/revoke_role/grant_permission/deny_permission/set_user_status (każdy zwraca `Result`). Infra: `Argon2Hasher`, `PyJWTTokenService` (access+refresh, rotacja, **reuse-detection**), repozytoria, mappery, UoW. Presentation: `/api/v1/{auth,users,admin/users}`, `requires(*codes)`. Migracje `0002`/`0003`. Testy unit + szkielet integration. DI w `container.py`. | ✅ |
| **2 — content** | Domain: `Post`, `Comment` (materialized `path` + `depth`), `Category`, `Tag`, VO `Slug`/`MarkdownContent`/`ContentFormat`. Application: create/update/delete post & comment, get_post, list_posts (keyset), comment_tree, kategorie, tagi, `pagination.py`. Infra: ORM (aliasy legacy + `tag_orm`), repozytoria, mappery, UoW z resolverem `user UUID → users.id`. Presentation: `/api/v1/{posts,comments,categories,tags}`. Migracje `0004` (kolumny content + `tags`/`post_tags` + **trigger FTS tsvector** + backfill `path` rekurencyjnym CTE) i `0005` (5 kategorii). Testy unit (path, pagination, VO). | ✅ kod gotowy — **ale niezaznaczone** w `TASKS.md`/`README.md` |

### Czego BRAKUJE (tylko szkielet `__init__.py` lub nic)

- **Faza 3 — files**: puste pakiety `modules/files/*`. Upload nadal realizuje **legacy** `routers/attachments.py`.
- **Faza 4 — RabbitMQ + notifications + audit**: puste pakiety; w użyciu `InMemoryEventBus` (eventy gubione). `aio-pika` jest w zależnościach, niewpięte.
- **Faza 5 — WebSocket**: pusty `modules/notifications/presentation/ws/`.
- **Faza 6 — widoki DB + FTS + keyset**: keyset i tsvector częściowo zrobione już w fazie 2; **widoki SQL nie istnieją**.
- **Faza 7 — observability**: `prometheus-fastapi-instrumentator` w zależnościach, niewpięte; brak `/metrics`, brak middleware (request-id, security headers).
- **Faza 8 — k8s polish**: jest `migration-job` + podstawowe manifesty; brak NetworkPolicy, PDB, CronJob, manifestów RabbitMQ, `ingress.yaml` (jest referowany w docs, ale nie istnieje).
- **Faza 9 — CI/CD**: brak `.github/`.
- **Frontend (przekrojowo)**: **stub**. `App.jsx` to sam nagłówek; `api.js` używa `baseURL:"/api"` (powinno `/api/v1`) i `localStorage` (projekt zakłada cookie httpOnly dla refresh). Brak stron logowania/rejestracji/listy postów. To największa luka względem wymagań „frontend w React".

---

## 2. Wykryte błędy i niespójności

Severity: 🔴 krytyczny · 🟠 wysoki · 🟡 średni · ⚪ niski/info. „Status: naprawione" = zrobione w tej sesji.

| # | Sev | Problem | Status / zalecenie |
|---|-----|---------|--------------------|
| 1 | 🔴 | **Alembic `DuplicateTable` przy `docker compose up`** — `relation "users" already exists`. Wolumen `postgres_data` przeżywa restart i zawiera tabele z ery `create_all` (v0.2). Alembic nie widzi `alembic_version`, więc puszcza `0001` od zera → kolizja. | **Naprawione**: dodany idempotentny guard w `0001_baseline.py` (`if sa.inspect(bind).has_table("users"): return`). Stara baza zostaje „stampnięta" 0001, a `0002+` dogrywają brakujące kolumny/tabele. **Natychmiastowy reset (zalecany w dev):** `docker compose down -v && docker compose up --build`. Zweryfikowane logiką SQLAlchemy 2.0. |
| 2 | 🟠 | **`alembic/env.py` nie importował ORM modułu content** → `target_metadata` bez `tags`/`post_tags`. `alembic revision --autogenerate` wygenerowałby **DROP** tych tabel. | **Naprawione**: dodany `import app.modules.content.infrastructure.orm`. Dodany komentarz, by przy fazie 3 dołożyć import ORM `files`. |
| 3 | 🟠 | **CORS niepoprawny dla cookie-auth**: `CORS_ALLOW_ORIGINS=["*"]` + `allow_credentials=True`. Przeglądarka **odrzuca** wildcard z credentials, a refresh leci jako cookie httpOnly. | Do zrobienia przy froncie (Track F / faza 3-pre): ustaw jawny origin, np. `["http://localhost:3000","http://forum.local"]`. Nie zostawiać `*` z `allow_credentials=True`. |
| 4 | 🟡 | **Legacy `attachments` używa `int post_id/comment_id`**, a `/api/v1/posts` zwraca `UUID public_id`. Front nie zmapuje jednego na drugie. | Rozwiązuje faza 3 (files po UUID). Do tego czasu uploady są de facto odcięte od nowego API. |
| 5 | 🟡 | **Async-over-sync**: wszystkie repo/UoW to `async def` na synchronicznym `Session`. W async-endpointach **blokuje to event loop** na czas I/O DB. | Akceptowalne przy obciążeniu studenckim (+`--workers 2`). Decyzja w osobnym kroku (sekcja 6, „Decyzja D1"): albo `AsyncSession`+asyncpg, albo endpointy `def` (threadpool). |
| 6 | ⚪ | **Legacy `decode_access_token` nie sprawdza `type`** — przyjąłby refresh jako access na starych endpointach. | Niskie ryzyko; znika z usunięciem legacy (faza 3). Można dodać `if payload.get("type")!="access": raise`. |
| 7 | ⚪ | **ADR-13 mówi UUID v7** (sortowalne czasowo), kod używa `uuid4`/`gen_random_uuid` (v4). | Keyset paginacja kompensuje to indeksem `(created_at, public_id)`. Albo zaktualizuj ADR-13 na „UUIDv4 + sort po created_at", albo wdroż `uuid6`/`uuid_utils` dla v7. |
| 8 | ⚪ | **`MAX_COMMENT_DEPTH`**: `docs/05` (faza 2) mówi „domyślnie 8", kod/`config.py`/`CLAUDE.md` = **5**. | Ujednolicone na **5** (kod jest źródłem prawdy). |
| 9 | ⚪ | **Sprzeczność w docs**: `ARCHITECTURE_PLAN §7` mówi „init container" do migracji, `§8` i implementacja używają **Job**. | Job wygrywa (brak race przy `replicas>1`). Usunąć wzmiankę o init-container. |
| 10 | ⚪ | **`/health/ready` zawsze zwraca ready** (TODO: DB/RabbitMQ). Probe niewiele znaczy. Backend deployment pinguje `/health` (legacy), compose `/health/live`. | Dokończyć w fazie 4/7; ujednolicić probe na `/health/ready`. |
| 11 | ⚪ info | **Stale tracking**: faza 2 zrobiona, ale odhaczona jako TODO w `TASKS.md`/`README.md`; `CLAUDE.md` opisuje strukturę v0.2 (legacy), nie modular monolith. | Zaktualizowane w tej sesji (`CLAUDE.md`, `TASKS.md`, `memory/`). |

---

## 3. Ocena architektury i jakości kodu

**Mocne strony (utrzymać ten poziom):**

- **Prawdziwa Clean Architecture**, nie fasada. Reguła zależności trzymana: `domain` nie importuje FastAPI/SQLAlchemy; porty to `Protocol`; use case'y zwracają `Result[T, DomainError]`; agregaty mają zachowanie i emitują `DomainEvent`; VO walidują w `__post_init__`.
- **Silne typowanie**: PEP 695 (`Ok[T]`, `type Result[...]`), `Annotated[..., Depends()]`, `mypy --strict`, bogaty zestaw reguł ruff (S/B/ASYNC/UP/N…).
- **Bezpieczeństwo**: Argon2id, access(15m)+refresh(14d), rotacja refresh + **reuse-detection** (rewok łańcucha + wszystkich sesji), cookie httpOnly, RBAC + per-user ACL (`effective_permissions = ∪ról ∪ grant \ deny`), generyczne „invalid credentials", RFC 5987 dla nazw plików.
- **Migracje**: konwencja nazw (stabilny autogenerate), seedy idempotentne (`ON CONFLICT`), trigger FTS, backfill `path` rekurencyjnym CTE, `batch_alter_table` (kompatybilność z SQLite w testach).
- **Pragmatyczny ORM przejściowy**: jedna klasa mapuje tabelę; `UserOrm`/`PostOrm`/… to **aliasy** klas legacy → brak podwójnego mapowania na `Base.metadata`.
- **Kontener**: multi-stage `uv`, użytkownik nie-root (uid 1000), healthcheck; w k8s migracja jako **Job**.

**Długi techniczne (świadome, do spłaty w fazach):**

- Async-over-sync (#5) — największy dług „poprawnościowy".
- Dwie warstwy równolegle (legacy + modules) — komplikuje czytanie; znika w fazach 3–4.
- `RoleId(UUID(int=int(row.id)))` — „phantom typing" int→UUID dla ról; działa, ale jest hackiem (komentarz w kodzie to przyznaje).
- DI ręczne w `container.py` (każdy `get_*_uc()` woła `get_*_uow()`); OK, ale rośnie liniowo — rozważyć fabrykę/parametr `Depends` współdzielący UoW per request.

**Werdykt:** jak na projekt studencki poziom jest wysoki — to portfolio-grade backend. Priorytety: (a) domknąć pętlę produktową (files → eventy → WS → observability), (b) **zbudować frontend**, (c) spłacić async-sync przed obroną jeśli ma być mowa o skalowaniu/HPA.

---

## 4. Co poprawić w starych instrukcjach (`docs/05`, ADR)

Te punkty **nadpisują** treść z `docs/05-implementation-phases.md` / `ARCHITECTURE_PLAN.md`:

1. **Faza 0 / kryterium „alembic upgrade head na bazie z create_all"** — to właśnie źródło błędu #1. Nowa reguła: **dev startuje z czystego wolumenu** (`down -v`), a `0001` ma guard. Nie zakładać „pustej migracji baseline".
2. **Faza 2**: `MAX_COMMENT_DEPTH` = **5** (nie 8). Path: zero-padded `lpad(id,8,'0')` segmenty łączone `.` — zgodnie z `0004`.
3. **Faza 3**: dopisać krok **migracji ID** — nowy `files` adresuje właścicieli przez **UUID** (`post.public_id`, `comment.public_id`, `user.public_id`), nie przez int. Stare `attachments` (int) + dane → zmigrować lub porzucić. `users.avatar_file_id` (BigInt) ma dostać FK do `files.id` dopiero gdy tabela `files` istnieje.
4. **Faza 4 vs 5 (WebSocket + worker)**: doprecyzowane — worker (consumer RabbitMQ) **nie trzyma** połączeń WS (te żyją w podach backendu). Mechanizm fan-out do WS: osobny event `notifications.NotificationCreated` z **per-pod exclusive/autoDelete queue**. W „prostej wersji" MVP: broadcast in-process w podzie backendu (akceptowalny trade-off, opisać w sprawozdaniu).
5. **ADR-13 (UUID v7)** vs kod (v4) — patrz #7. Zdecydować i ujednolicić.
6. **ARCHITECTURE_PLAN §7** — usunąć „init container", zostaje **Job** (§8).
7. **Wszędzie „Opus 4.6"** → nieaktualne. Prompty startowe działają z dowolnym aktualnym modelem; nie przywiązywać do wersji.
8. **Brakuje tracku Frontend** — dodany niżej (Track F). `docs/05` traktuje front marginalnie (tylko hook WS w fazie 5), a to twardy wymóg projektu.

---

## 5. Pułapki — czego NIE powtarzać (must-read przed każdą fazą)

1. **Alembic + wolumen**: po każdej zmianie schematu w dev rób `docker compose down -v` (albo `scripts/reset-db.ps1` w k8s). Nigdy nie licz na „auto-naprawę" migracji na brudnym wolumenie. `0001` ma teraz guard, ale to siatka bezpieczeństwa, nie zaproszenie do bałaganu.
2. **Mount-lag (workspace)**: po edycji pliku narzędziami plikowymi bash może przez kilka–kilkanaście sekund widzieć **starą/uciętą** wersję (potrafi zgłosić fałszywy `SyntaxError`). Weryfikuj świeżo zapisany kod narzędziem Read, nie `cat` z mounta; albo odczekaj.
3. **Po dodaniu nowej tabeli ORM**: **dopisz import jej pakietu ORM w `alembic/env.py`** — inaczej `--autogenerate` wygeneruje DROP (błąd #2).
4. **CORS + cookie**: nigdy `allow_origins=["*"]` z `allow_credentials=True`. Jawny origin.
5. **Nowe migracje na Postgres**: typy dialektowe (`postgresql.ENUM`, `TSVECTOR`, `INET`, `UUID`) twórz przez wzorzec z `0002`/`0004` (`create_type=False` + `.create(bind, checkfirst=True)`), z gałęzią `else` dla SQLite (testy).
6. **`index=True` na kolumnie ORM** generuje `ix_*` wg konwencji nazw z `shared/.../db/base.py` — w migracji używaj **tych samych nazw**, by autogenerate nie „dryfował".
7. **Spójność legacy↔nowe role**: repo identity zapisuje równolegle `users.role` (legacy) i `user_roles` (RBAC). Każda nowa ścieżka zmiany roli **musi** przechodzić przez agregat `User` + repo, inaczej panel admina (czyta `users.role`) rozjedzie się z RBAC.
8. **`expire_on_commit=False`** jest ustawione — po `commit()` obiekty ORM są nadal użyteczne; nie zakładaj odwrotnie.

---

## 6. Decyzje do podjęcia (zanim ruszą kolejne fazy)

- **D1 — async vs sync DB** (blokuje „czystą" fazę 4/5/6): rekomendacja na obronę pod HPA → albo (a) `AsyncSession` + `psycopg` async (repo realnie `await`), albo (b) endpointy `def` (FastAPI threadpool) i UoW sync. Najmniej pracy: (b). Najlepiej „na pokaz": (a).
- **D2 — UUID v7** (ADR-13): wdrożyć `uuid_utils`/`uuid6` czy zostać przy v4 + sort po `created_at`? Rekomendacja: zostać przy v4 (działa), zaktualizować ADR.
- **D3 — kiedy usunąć legacy** (`core/models/routers/services/schemas` + admin SSR): admin SSR jest wartościowy na demo. Rekomendacja: legacy `attachments` usunąć w fazie 3; admin SSR **przepisać** na permission `user.manage`/`audit.read` na bazie nowego JWT w fazie 7 (lub zostawić jako świadomy „legacy island", ale wtedy nie kasować `core/security.py`).

---

## 7. Skorygowana roadmapa — szczegółowe instrukcje faz 3–9 + Frontend

> Format każdej fazy: **Cel · Pliki · Kroki · Migracje · Kryteria odbioru · Pułapki**.
> Pełny kontekst architektoniczny dalej w `docs/01–04`; tu są poprawki i konkrety wykonawcze.
> Kolejność rekomendowana: **F3 → F-Front (MVP) → F4 → F5 → F7 → F6 → F8 → F9**, z D1 podjętą przed F4.

### Faza 3 — moduł `files` (generyczny upload) — **następna**

**Cel.** Jeden zestaw endpointów `/api/v1/files` dla avatarów, załączników postów i komentarzy; metadane w DB, bajty na dysku (PVC). Usunięcie legacy `attachments`.

**Pliki:**
```
modules/files/
  domain/        file.py (File AR), value_objects.py (StorageKey, Sha256, MimeType, ByteSize), events.py (FileUploaded, FileDeleted)
  application/   ports.py (IFileRepository, IFileStorage, IFilesUnitOfWork), commands.py, use_cases/{upload_file,download_file,delete_file,get_file_info}.py
  infrastructure/ orm/file_orm.py, repositories/file_repo.py, storage/local_disk.py, mappers.py, unit_of_work.py
  presentation/  routers/files.py, dto/file_dto.py
```

**Kroki:**
1. Domain `File` AR: pola `id(UUID)`, `uploader_id(UserId)`, `storage_key`, `original_name`, `content_type`, `size_bytes`, `sha256`, `owner_type∈{post,comment,user_avatar}`, `owner_id(UUID|None)`. Metody `attach_to(owner_type, owner_id)`, `detach()`. VO: `MimeType` (whitelist z `settings.ALLOWED_MIME_TYPES`), `ByteSize` (≤ `MAX_UPLOAD_SIZE_BYTES`), `Sha256`.
2. `IFileStorage` (port): `save(stream)->StorageKey`, `open_for_read(key)->IO`, `delete(key)`. Impl `LocalDiskStorage` — **streaming** (chunki, bez ładowania do RAM), nazwa = `f"{uuid4().hex}{ext}"`, podkatalogi `aa/bb/` z prefiksu sha256 (uniknięcie wielkich katalogów).
3. MIME sniffing `python-magic` z faktycznej zawartości (nie ufaj `content_type` z klienta); walidacja po sniffingu → 415 przy złym typie.
4. Use case `upload_file`: oblicz sha256 podczas streamingu; dedup opcjonalny (ten sam sha256 + uploader → zwróć istniejący). Sprawdź uprawnienia: `file.upload`; dla `owner_type=post` zweryfikuj że post istnieje (przez port do content lub event) i że actor=autor lub `post.update.any`.
5. Presentation: `POST /api/v1/files?owner_type=&owner_id=` (multipart), `GET /api/v1/files/{id}` (StreamingResponse + RFC 5987), `GET /api/v1/files/{id}/info`, `DELETE /api/v1/files/{id}` (uploader lub `file.delete.any`). „Cukier": `POST /api/v1/posts/{post_id}/files` deleguje do generyka (bez duplikacji logiki).
6. Integracja identity: `User.set_avatar(file_id)` (jest) + `POST /api/v1/users/me/avatar` (upload→set_avatar→event `AvatarChanged`; odepnij stary plik). Dodaj FK `users.avatar_file_id → files.id` w migracji.
7. **Usuń legacy**: `routers/attachments.py`, `services/attachment_service.py`, `services/storage_service.py`, `models/attachment.py`, `schemas/attachment.py`; zdejmij include w `main.py`; usuń z ruff/mypy `extend-exclude`. Admin SSR `attachments.html` — podmień na listę z `files` albo usuń stronę.
8. **`alembic/env.py`**: dodaj `import app.modules.files.infrastructure.orm` (patrz pułapka #3).

**Migracje:** `0006_create_files_table.py` — `files` (UUID public_id unique, sha256 index, `owner_type` enum, `owner_id` UUID, XOR/`CHECK` na ownership), backfill ze starych `attachments` (mapuj `post_id→post.public_id`) **albo** świadomie porzuć stare dane (dev). Dodaj FK `users.avatar_file_id`.

**Kryteria odbioru:** jeden endpoint obsługuje avatar + załącznik posta + komentarza; sniffing MIME → 415 dla złych typów; `GET` streamuje; `DELETE` respektuje własność; sha256 liczone; brak importów `app.routers.attachments` w całym repo (`grep`).

**Pułapki:** ID po UUID (nie int) — błąd #4; `python-magic` na Windows wymaga `python-magic-bin` (jest w deps warunkowo); guard #3 w `env.py`.

### Faza 3-pre / Track F (MVP) — Frontend React (brakujący track)

> Wstaw przynajmniej MVP frontu wcześnie — to wymóg projektu, a integracja ujawnia błędy API (CORS, kształt DTO). Sugerowane przeplatać z F3.

**Cel.** Działający SPA: rejestracja, logowanie (z refresh-flow), lista postów (keyset), widok posta z drzewem komentarzy (markdown render + DOMPurify), tworzenie posta/komentarza, profil.

**Kroki:**
1. **Napraw `api.js`**: `baseURL:"/api/v1"`, `withCredentials:true` (cookie refresh). Access token trzymaj **w pamięci** (zmienna modułu / React context), **nie** w `localStorage` (XSS). Interceptor 401 → wywołaj `POST /auth/refresh` (cookie) → ponów żądanie; przy porażce → logout.
2. **Napraw CORS backendu** (błąd #3) — jawny origin + `allow_credentials=True`.
3. Routing (React Router 6): `/`, `/login`, `/register`, `/posts/:id`, `/new`, `/me`. `AuthContext` (access token + user + permissions z `/auth/me`).
4. Komponenty: `PostList` (infinite scroll po `cursor`), `PostView` (markdown-it + DOMPurify; drzewo komentarzy po `path`), `CommentForm` (z `parent_id`), `PostForm`, `LoginForm`, `RegisterForm`, `Navbar` (role-aware).
5. Obsługa błędów: czytaj kopertę `{error:{code,message,field}}` z backendu.
6. Build: Vite → nginx (Dockerfile jest); `imagePullPolicy: Never` w k8s.

**Kryteria odbioru:** pełny flow w przeglądarce: register→login→lista→post→komentarz; odświeżenie strony nie wylogowuje (refresh działa); render markdown bezpieczny (DOMPurify); brak tokenów w `localStorage`.

**Pułapki:** CORS+credentials (#3); endpoint `/api/v1` nie `/api`; po `DELETE` komentarza UI pokazuje „[usunięto]" (soft delete), dzieci zostają.

### Faza 4 — RabbitMQ + `notifications` + `audit`

**Cel.** Realny event bus (at-least-once), konsumenci w osobnym procesie.

**Pliki:** `shared/infrastructure/eventbus/rabbitmq.py` (`RabbitMQEventBus` na `aio-pika`, exchange `forum.events` topic, DLX `forum.events.dlx`), `modules/audit/*` (handler `#`→`audit_log`, `GET /api/v1/admin/audit`), `modules/notifications/*` (`Notification`, handlery `on_post_created`/`on_comment_added`, `GET /api/v1/notifications`, `POST /…/{id}/read`), `app/worker.py` (entrypoint consumerów), `k8s/rabbitmq/*`, `k8s/backend/worker-deployment.yaml`.

**Kroki:**
1. **Najpierw D1** (async). `RabbitMQEventBus.publish` serializuje event (typ + payload JSON + `occurred_at` + `event_id`), routing_key = `f"{module}.{EventName}"`.
2. DI: w procesie web użyj `RabbitMQEventBus` do publish; konsumpcję uruchom **tylko** w `worker.py`. Testy: `InMemoryEventBus`.
3. `audit`: queue `audit.all` bind `#`; idempotencja po `event_id`.
4. `notifications`: queue per typ; bez systemu followersów twórz powiadomienie dla autora posta (komentarz) / dla admina (nowy post) — pokaz mechanizmu.
5. DLQ: `x-dead-letter-exchange`; po N retry → DLX. Pokaż w RabbitMQ management UI.
6. Health: `/health/ready` sprawdza DB + połączenie RabbitMQ (błąd #10).

**Migracje:** `0007_create_notifications.py`, `0008_create_audit_log.py`.

**Kryteria odbioru:** `POST /api/v1/posts` → wpis w `audit_log` + `Notification`; management UI pokazuje exchange/queues/DLX; restart workera nie gubi (kolejki durable).

**Pułapki:** worker i web to **osobne procesy** — nie współdziel singletonów in-memory; eventy muszą lecieć przez broker, nie przez `InMemoryEventBus`.

### Faza 5 — WebSocket (prosta wersja)

**Cel.** Live powiadomienia dla zalogowanego usera.

**Pliki:** `modules/notifications/presentation/ws/{connection_manager.py,notifications.py}`, `shared/presentation/deps.py::get_current_user_ws`, `k8s/ingress.yaml` (sticky cookie).

**Kroki:** `ConnectionManager` (singleton per pod, `dict[user_id→set[WebSocket]]`); endpoint `/ws/notifications` (auth: `?token=` lub pierwszy msg; `decode_access`); pętla z `WebSocketDisconnect`. Fan-out: zob. sekcja 4.4 — MVP = broadcast in-process w podzie backendu, który zapisał `Notification`; wariant pełny = per-pod exclusive queue na `notifications.NotificationCreated`. Ingress `nginx.ingress.kubernetes.io/affinity: cookie`. Front: hook `useWebSocket(token)` + toast.

**Kryteria odbioru:** komentarz pod postem usera → push WS w czasie rzeczywistym (gdy spięty z repliką zdarzenia — świadomy trade-off). Reconnect działa.

**Pułapki:** WS auth nie przejdzie nagłówkiem `Authorization` z przeglądarki — użyj query param lub subprotocol; token krótkożyjący (15m) → reconnect po refresh.

### Faza 6 — widoki DB + FTS + keyset (część już jest)

**Cel.** Dociągnąć widoki SQL i search; keyset/tsvector z fazy 2 zrewidować.

**Pliki/Migracje:** `0009_create_views.py` (`v_posts_with_stats`, `v_user_effective_permissions`, `v_comment_tree_lite`, `v_top_posters_30d`), `use_cases/search_posts.py`. Repozytoria content czytają z widoków.

**Kroki:** endpoint `GET /api/v1/posts/search?q=` na `search_tsv @@ websearch_to_tsquery('simple', :q)` (trigger już utrzymuje `search_tsv`). Listing przez `v_posts_with_stats` (post + #komentarzy + autor jednym JOIN). `EXPLAIN ANALYZE` w teście — brak `Seq Scan` na `posts`.

**Kryteria odbioru:** 1000 fake postów, paginacja 20/strona bez Seq Scan; search po polskim słowie zwraca trafienia.

**Pułapki:** `to_tsvector('simple')` nie robi stemmingu PL — to świadomy wybór (brak słownika PL); udokumentuj.

### Faza 7 — observability (Prometheus + Grafana + structlog)

**Cel.** `/metrics`, structured logs z `request_id`, dashboard.

**Pliki:** `shared/infrastructure/metrics.py`, `shared/presentation/middleware/{request_logging.py,security_headers.py}`, `k8s/monitoring/{prometheus-values.yaml,servicemonitor-backend.yaml,dashboards/forum-overview.json}`.

**Kroki:** `prometheus-fastapi-instrumentator` (jest w deps) → `/metrics`. Middleware: `X-Request-ID` + `structlog.contextvars`; security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP). Custom: `Counter` posts/comments/login_failures/events_published, `Histogram` use_case_duration (dekorator `@timed`). Helm `kube-prometheus-stack` w ns `monitoring`; `ServiceMonitor`; dashboard JSON (HTTP rate/error/p95, aktywność domenowa, repliki HPA, głębokości kolejek RabbitMQ).

**Kryteria odbioru:** Grafana „Forum Overview" pokazuje metryki; `forum_posts_created_total` rośnie po POST.

### Faza 8 — k8s polish

**Pliki:** `k8s/{backend,postgres,rabbitmq}/networkpolicy.yaml`, `k8s/backend/{cleanup-cronjob.yaml,poddisruptionbudget.yaml}`, HPA backend, `scripts/deploy.ps1` refactor.

**Kroki:** NetworkPolicy (backend egress: postgres+rabbitmq+DNS; postgres/rabbitmq ingress tylko z odpowiednich labeli); CronJob `cleanup-refresh-tokens` (@daily, `python -m app.maintenance.cleanup_refresh_tokens`); PDB `minAvailable:1`; HPA 2–6 (CPU). Probe → `/health/ready`.

**Kryteria odbioru:** `kubectl apply -f k8s/` idempotentne; NetworkPolicy widoczne; CronJob czyści wygasłe tokeny; PDB blokuje zdjęcie wszystkich replik naraz.

### Faza 9 — CI/CD + E2E

**Pliki:** `.github/workflows/{ci.yml,build-images.yml}`, `tests/e2e/test_full_user_flow.py`, `Makefile`.

**Kroki:** CI = `uv sync` → `ruff check .` → `mypy app/` → `pytest -m "not integration"` (+ job z usługą Postgres dla integration). `build-images.yml` na tag `v*` → `ghcr.io`. E2E: testcontainers Postgres(+RabbitMQ) + `httpx.AsyncClient(app=create_app())`: register→login→me→(admin) create category→create post→comment→list→upload avatar.

**Kryteria odbioru:** zielony CI badge; `make test` lokalnie zielony.

---

## 8. Backlog drobnych poprawek (1–2 linijki, przy okazji)

- [ ] CORS: jawny origin (#3) — przy starcie frontu.
- [ ] `/health/ready`: realny check DB (`SELECT 1`) — faza 4.
- [ ] Backend deployment probe → `/health/ready` zamiast `/health`.
- [ ] Legacy `decode_access_token`: odrzucać `type!="access"` (#6) — albo usunąć z legacy.
- [ ] `configmap.yaml`: `SECRET_KEY` przenieść do Secret (jest TODO w komentarzu).
- [ ] `pyproject.toml`: po fazie 3 usunąć `python-jose`/`passlib` (legacy auth) i `extend-exclude` dla usuniętych folderów.
- [ ] Zaznaczyć fazę 2 jako done w `TASKS.md`/`README.md` (zrobione w tej sesji).
- [ ] ADR-13: ujednolicić UUID v4 vs v7 (#7).

---

## 9. Jak prowadzić kolejne sesje

1. „Robimy **Fazę N** wg `docs/07-audyt-i-dalsze-instrukcje.md` (sekcja 7)."
2. Model czyta tę fazę + `docs/01–04` dla detali + sekcję 5 (pułapki) **zawsze**.
3. Implementacja → testy → `ruff`/`mypy` → po skończeniu update `TASKS.md` i `memory/`.
4. Po każdej zmianie schematu: nowa migracja + import ORM w `env.py` + `down -v` w dev.
