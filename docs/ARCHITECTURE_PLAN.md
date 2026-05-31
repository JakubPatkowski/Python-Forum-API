# Forum Wędkarskie — Plan Architektury v3

> **Cel dokumentu.** Pełny, jednoznaczny plan przekształcenia obecnego projektu (FastAPI + React + minikube,
> warstwowo: models / schemas / services / routers) w **modular monolith** opartą o **Clean Architecture**,
> z RabbitMQ, observability (Prometheus + Grafana), refresh-tokenami w DB, prostym WebSocketem,
> migracjami Alembic, widokami SQL i pełnym RBAC + ACL.
>
> Dokument ma być wystarczająco szczegółowy, by w kolejnych sesjach z **Opus 4.6** wystarczyło
> wskazać fazę i plik z `docs/` — model dostanie pełen kontekst.

---

## 0. Decyzje architektoniczne (ADR — krótka forma)

| ID  | Decyzja                                                                  | Uzasadnienie |
|-----|--------------------------------------------------------------------------|--------------|
| ADR-1 | **Modular monolith**, nie mikroserwisy                                 | Jedna baza danych, jeden proces — najtańszy w utrzymaniu i deployu, a moduły z jasnym kontraktem dadzą się wydzielić później. Mikroserwisy = za dużo overheadu na projekt studencki. |
| ADR-2 | **Clean Architecture** — 4 warstwy (domain / application / infrastructure / presentation) | Czysta granica między regułami biznesowymi a frameworkiem. Domain nie zna FastAPI ani SQLAlchemy. |
| ADR-3 | **RabbitMQ** jako broker zdarzeń między modułami i instancjami         | Wybór użytkownika. Gwarancje at-least-once, retry, DLQ — efektowne na obronie. |
| ADR-4 | **PostgreSQL** jako jedyny store, **Redis** jako cache + WS state (opcjonalnie w fazie 8) | Postgres ma wszystko czego potrzebujemy (UUID, JSONB, widoki, partial indexes). Redis nie jest na MVP konieczny. |
| ADR-5 | **PyJWT** + refresh-token whitelist w tabeli `refresh_tokens`           | Wybór użytkownika. Proste, audytowalne, łatwo wylogować wszystkie sesje. |
| ADR-6 | **Argon2** do haszowania haseł (`argon2-cffi`) zamiast bcrypt          | Argon2id jest nowszym standardem OWASP. Bcrypt też OK, ale Argon2 wygląda lepiej w sprawozdaniu. |
| ADR-7 | **Alembic** do migracji, koniec z `create_all`                         | Migracje wersjonowane, możliwość downgrade, czytelna historia zmian schematu. |
| ADR-8 | **WebSocket — prosta wersja** (single replica obsługuje połączenie)     | Wybór użytkownika. Kompromis: pokazujemy WS, ale bez backplane'u. W k8s sticky sessions w Ingress. |
| ADR-9 | **Observability**: Prometheus + Grafana (Helm). Logi strukturalne JSON (`structlog`) do stdout. | Wybór użytkownika. Loki pominięte — Prometheus zostawia dużo na pokaz, logi z `kubectl logs` wystarczą. |
| ADR-10 | **HPA** (Horizontal Pod Autoscaler) na `backend` deployment            | Pokazuje, że aplikacja jest stateless w warstwie HTTP (z wyjątkiem WS) i skaluje się poziomo. |
| ADR-11 | **RBAC + ACL**: rola = bundle uprawnień; opcjonalny per-user override | Rozwiązuje wymóg "jeden admin może mieć inne uprawnienia niż inny". |
| ADR-12 | **Język w kodzie: angielski** (nazwy, komentarze). Dokumentacja `docs/` po polsku. | Wymóg użytkownika. Łatwiej będzie podlinkować repo do CV. |
| ADR-13 | **UUID v4** jako klucze publiczne (`PublicId`), `bigserial` jako PK wewnętrzny | Schowanie sequence ID w API ma walor bezpieczeństwa. Sortowanie po `(created_at, public_id)` zamiast UUID v7. |
| ADR-14 | **MinIO (S3) + presigned URLs**, metadane w DB                        | Jeden generyczny endpoint `/api/v1/files/*` do wszystkiego (avatar / post / comment / category). Bajty poza backendem. |

---

## 1. Stack v3

| Warstwa            | Technologia                                                                            |
|--------------------|----------------------------------------------------------------------------------------|
| Język              | Python 3.12, type hints, `mypy --strict` (cel)                                         |
| Framework HTTP     | FastAPI + Uvicorn (production: `--workers 2`)                                          |
| Walidacja          | Pydantic v2                                                                            |
| ORM                | SQLAlchemy 2.0 (styl deklaratywny + `Mapped[...]`)                                     |
| Migracje           | Alembic                                                                                |
| Baza               | PostgreSQL 16                                                                          |
| Cache (opcjonalne) | Redis 7 (Token blocklist? Cache? — patrz faza 8)                                       |
| Broker             | RabbitMQ 3.13 + biblioteka `aio-pika`                                                  |
| Auth               | PyJWT + Argon2 (`argon2-cffi`) + refresh-tokens-whitelist w DB                         |
| WebSocket          | FastAPI native WS + `websockets`                                                       |
| Logging            | `structlog` (JSON do stdout)                                                            |
| Metryki            | `prometheus-fastapi-instrumentator` + custom `Counter`/`Histogram`                     |
| Testy              | `pytest` + `pytest-asyncio` + `httpx.AsyncClient` + `testcontainers` dla Postgres      |
| Frontend           | React 18, Vite, React Router 6, Axios, markdown-it + DOMPurify, pnpm                  |
| Konteneryzacja     | Docker (multi-stage frontend), `imagePullPolicy: Never` dla minikube                   |
| Orkiestracja       | minikube, Helm 3 (Prometheus, Grafana, RabbitMQ chart Bitnami), Ingress NGINX          |

---

## 2. Wysokopoziomowa architektura (text-diagram)

```
                      ┌──────────────────────────────────────────────────────┐
                      │                  Ingress NGINX                       │
                      │  - sticky sessions (cookie) na /ws/*                  │
                      └──┬───────────────────────┬───────────────────────────┘
                         │ /api/*, /ws/*         │ /
                         ▼                       ▼
                ┌────────────────┐       ┌────────────────┐
                │  backend (N x) │       │  frontend (Nx) │
                │  FastAPI       │       │  React + nginx │
                │  WS endpoint   │       └────────────────┘
                └────┬──────┬────┘
                     │      │
                     │      └──── publish/consume ─────┐
                     │                                  ▼
                     │                       ┌────────────────────┐
                     │                       │     RabbitMQ       │
                     │                       │  exchange: forum   │
                     │                       │  queues per-module │
                     │                       └────────────────────┘
                     ▼
              ┌─────────────┐
              │ PostgreSQL  │ ── views: post_with_stats, comment_tree, etc.
              └─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │   MinIO     │  (S3 storage)
              └─────────────┘

         Prometheus  scrape  ─►  backend /metrics   ──► Grafana dashboards
```

---

## 3. Warstwy Clean Architecture (skrócone)

Pełny opis: `docs/01-clean-architecture.md`.

1. **Domain** — czyste reguły biznesowe, brak importów zewnętrznych frameworków.
   - `Entity`, `AggregateRoot`, `ValueObject`, `EntityId[T]`, `DomainEvent`.
   - Encje: `User`, `Post`, `Comment`, `Category`, `Tag`, `File`, `Role`, `Permission`.
2. **Application** — use cases (np. `CreatePostUseCase`), porty (interfejsy repozytoriów, event busa).
   - `IRepository[T]`, `IUnitOfWork`, `IEventBus`, `IFileStorage`, `IPasswordHasher`, `ITokenService`.
3. **Infrastructure** — implementacje portów: SQLAlchemy, RabbitMQ, MinIO storage, Argon2, PyJWT.
4. **Presentation** — FastAPI routers, Pydantic DTO, dependency injection, mapery domain ↔ DTO.

**Reguła zależności:** strzałka tylko do środka. Domain ← Application ← Infrastructure / Presentation.

---

## 4. Moduły (modular monolith)

Pełny opis: `docs/01-clean-architecture.md`.

| Moduł          | Odpowiedzialność                                                          | Główne agregaty            | Eventy publikowane                 |
|----------------|---------------------------------------------------------------------------|----------------------------|------------------------------------|
| `shared`       | Bazowe abstrakcje (`Entity`, `Repository`, error envelope, `Result`)      | —                          | —                                  |
| `identity`          | Tożsamość, role, uprawnienia, JWT, refresh tokens                          | `User`, `Role`, `Permission` | `UserRegistered`, `UserBlocked`    |
| `content`      | Posty, komentarze (dowolnie zagnieżdżone), tagi, kategorie                 | `Post`, `Comment`          | `PostCreated`, `CommentAdded`      |
| `files`        | Upload / download / delete plików (avatary, embed w postach, załączniki)  | `File`                     | `FileUploaded`, `FileDeleted`      |
| `notifications`| Konsument eventów; subskrypcje, push do WS                                 | `Notification`             | (consumer)                          |
| `audit`        | Audyt akcji w systemie (consumer wszystkich eventów)                       | `AuditEntry`               | (consumer)                          |

**Komunikacja między modułami: tylko przez eventy lub publiczny port `__init__.py` (interfejsy).**
Bezpośrednie importy do prywatnych klas modułu są zabronione (egzekwowane przez konwencję +
linter `import-linter` — opcjonalnie).

---

## 5. Schemat DB i widoki

Pełny opis: `docs/02-database-schema.md`.

Tabele główne:

```
users(id, public_id, username, email, password_hash, avatar_file_id, is_active, created_at)
roles(id, name, description)
permissions(id, code, description)                     -- code: 'post.create', 'comment.delete.any'
role_permissions(role_id, permission_id)               -- ACL: rola → uprawnienia
user_roles(user_id, role_id)                           -- użytkownik → role (M:N)
user_permissions(user_id, permission_id, granted)      -- per-user override (granted=true/false)

refresh_tokens(id, user_id, token_hash, expires_at, revoked_at, replaced_by, user_agent, ip)

categories(id, public_id, name, slug, description)
tags(id, name, slug)
post_tags(post_id, tag_id)

posts(id, public_id, author_id, category_id, title, slug, content, content_format,
      created_at, updated_at)
comments(id, public_id, post_id, parent_id, author_id, content, content_format,
         depth, path,        -- ltree-like path: '1.5.12' do szybkich subtree queries
         is_deleted, created_at, updated_at)

files(id, public_id, uploader_id, storage_key, original_name, content_type,
      size_bytes, sha256, owner_type, owner_id,   -- generyczny owner (post / comment / user-avatar / null)
      created_at)

audit_log(id, actor_user_id, event_type, target_type, target_id, payload_json, created_at)
```

Widoki (pełna lista w `docs/02-database-schema.md`):

- `v_posts_with_stats` — post + COUNT(comments) + COUNT(attachments) + autor (jeden JOIN dla listingu)
- `v_user_permissions` — efektywny zestaw uprawnień użytkownika (UNION ról + override)
- `v_comment_tree` — z rekurencyjnym CTE, materializowany na żądanie
- `v_top_posters_30d` — ranking użytkowników z ostatnich 30 dni

---

## 6. Bezpieczeństwo

Pełny opis: `docs/03-security.md`.

- **Argon2id** dla haseł (parametry: time=3, memory=64MiB, parallelism=4).
- **JWT access** krótki (15 min) — bez state, z `sub=user.public_id` i `permissions:[...]`.
- **JWT refresh** długi (14 dni) — wpisywany do `refresh_tokens` jako hash (sha256), przy refreshu rotujemy.
  Detekcja reuse: stary refresh + jego potomek już uniewazniony → revoke wszystkie sesje usera.
- **Dependency injection** uprawnień w endpointach:
  ```python
  @router.delete("/posts/{post_id}")
  async def delete_post(
      post_id: PostId,
      _: Annotated[User, Depends(requires("post.delete.own | post.delete.any"))],
  ) -> None: ...
  ```
- **Walidacja plików**: MIME sniffing (`python-magic`), max size, generowanie nazw, sha256 dedup.
- **Rate limiting** na `/api/auth/*` (`slowapi`).
- **Security headers** middleware (HSTS, CSP, X-Content-Type-Options).
- **CORS** zacieśniony do origin frontend service.

---

## 7. Infrastruktura k8s

Pełny opis: `docs/04-infrastructure.md`.

- **Namespace:** `forum-wedkarskie`.
- **Deployments:** backend (replicas: 2, HPA 2–6), frontend (replicas: 2), postgres (1, PVC), rabbitmq (1, PVC), minio (1, PVC), pgadmin (1).
- **Charts (Helm):** `bitnami/rabbitmq`, `prometheus-community/kube-prometheus-stack`.
- **Ingress NGINX:**
  - `/api/*` → backend (round-robin)
  - `/ws/*` → backend z `nginx.ingress.kubernetes.io/affinity: "cookie"` (sticky sessions)
  - `/` → frontend
- **PVC `uploads-pvc`** — legacy (po fazie 3 bajty ida do MinIO). Moze zostac jako zgodnosc
  dla starego kodu lub zostac usuniety po pelnym przejsciu na files.
- **NetworkPolicy:** backend → postgres tylko z odpowiednim label selectorem.
- **Probes:** liveness, readiness, **startup** (Alembic upgrade head trwa kilka sekund).
- **Migration Job:** `alembic upgrade head` jako Kubernetes Job przed startem aplikacji (nie init-container — unikamy race condition przy `replicas>1`).

---

## 8. Komunikacja między instancjami

Pytanie z briefingu: *"jak instancje będą się synchronizować?"*

Odpowiedź — w naszej architekturze są dwa typy stanu:

1. **Trwały stan domeny** → PostgreSQL. Każda instancja czyta z tej samej bazy.
   Brak desynchronizacji bo brak lokalnego cache'u stanu domeny.
2. **Notyfikacje / cross-cutting events** → RabbitMQ. Moduł publikuje event (`PostCreated`),
   inne moduły (notifications, audit) konsumują **niezależnie**.

WebSocket w "prostej wersji" (wybrany wariant): połączenie WS *trzyma jedna replika*.
Ingress kieruje do tej samej repliki przez sticky-cookie. Notyfikacje broadcastowane wewnątrz repliki
do lokalnych subskrybentów. **Ograniczenie:** powiadomienie o akcji wykonanej w replice A
nie dotrze do klienta WS spiętego z repliką B. W dokumentacji opisujemy to jako świadomy trade-off
(z możliwością dodania backplane Redis Pub/Sub w fazie 2).

**Tabela `refresh_tokens` + cache wewnątrz pojedynczej repliki** — niespójności brak, bo
każdy refresh idzie do DB. Wylogowanie userów = SQL UPDATE.

**Migracje** — `alembic upgrade head` jako **Kubernetes Job** uruchamiany przed rollout
(`kubectl apply` ręcznie lub `helm hook pre-install,pre-upgrade`).
Job gwarantuje, że migracja zakończy się zanim pody aplikacji wystartują,
eliminując race condition przy `replicas: N`. Patrz `docs/04-infrastructure.md`.

---

## 9. Czego brakuje (rzeczy, o których warto pomyśleć)

Listę z briefingu uzupełniam o:

- **CI/CD** — GitHub Actions: lint (ruff, mypy), test (pytest), build images, push do registry,
  deploy do minikube via skaffold (lub `kubectl apply` w jobie). Konkretny pipeline w `docs/05-implementation-phases.md`.
- **API versioning** — `/api/v1/...`. Daje miejsce na zmiany bez breaking change.
- **OpenAPI tagi i `operation_id`** — czytelny Swagger, generowanie klienta TS na frontendzie.
- **Pagination + sorting + filtering** — wzorzec keyset pagination dla list postów / komentarzy.
- **Idempotency-Key** na POST endpoints podatne na powtórzenia (uploady, register).
- **Soft delete** dla komentarzy (zachowanie struktury drzewa po usunięciu rodzica).
- **Searchability** — `tsvector` w `posts` (Postgres FTS) z GIN indeksem, później ewentualnie OpenSearch.
- **Health endpoints** — `/health/live` (czy proces żyje), `/health/ready` (czy DB + RabbitMQ odpowiada).
- **Konfiguracja per-environment** — `pydantic-settings` + osobne ConfigMapy/Secrety per env.
- **Testy integracyjne** z `testcontainers` (real Postgres, real RabbitMQ).
- **Linter granic modułów** — `import-linter` z kontraktami "module X nie importuje module Y prywatnie".
- **`sentry-sdk`** (opcjonalnie) — error tracking, gratis dla studentów / open source.

---

## 10. Mapa dokumentów

| Plik                                       | Zawartość                                                                |
|--------------------------------------------|--------------------------------------------------------------------------|
| `docs/ARCHITECTURE_PLAN.md` *(ten plik)*   | Master plan, decyzje (ADR), wysokopoziomowy obraz                       |
| `docs/01-clean-architecture.md`            | Warstwy, abstrakcje (Entity / ValueObject / Repository / EventBus), moduły |
| `docs/02-database-schema.md`               | Pełny schemat, indeksy, widoki, Alembic baseline                         |
| `docs/03-security.md`                      | JWT (access + refresh), Argon2, RBAC + ACL, walidacja plików, headers   |
| `docs/04-infrastructure.md`                | k8s manifesty (cele), RabbitMQ, Prometheus + Grafana, HPA, NetworkPolicy |
| `docs/05-implementation-phases.md`         | Fazy 0–9 z checklistami, kryteria gotowości, prompty dla Opus 4.6        |

---

## 11. Roadmapa (fazy)

Pełny opis: `docs/05-implementation-phases.md`. W skrócie:

| Faza | Cel                                                                                | Estymowany czas |
|------|------------------------------------------------------------------------------------|-----------------|
| 0    | Setup: Alembic, struktura katalogów v3, `shared/` abstrakcje, English-only rename | 1 sesja         |
| 1    | Moduł `identity`: User domain, role, permissions, JWT, refresh tokens                   | 2 sesje         |
| 2    | Moduł `content`: Post, Comment (rekurencja przez `path`/`ltree`), Tag, Category    | 2 sesje         |
| 3    | Moduł `files`: generyczny upload + storage adapter + metadata                      | 1 sesja         |
| 4    | Event bus (RabbitMQ): `IEventBus`, publishery, konsumenci `audit` + `notifications`| 1 sesja         |
| 5    | WebSocket: notyfikacje per-user, sticky sessions Ingress                            | 1 sesja         |
| 6    | DB widoki + FTS + pagination keyset                                                 | 0.5 sesji       |
| 7    | Observability: structlog + Prometheus + Grafana dashboardy                          | 1 sesja         |
| 8    | k8s: RabbitMQ chart, HPA, migration job, NetworkPolicy, opcjonalnie Redis           | 1 sesja         |
| 9    | CI/CD GitHub Actions, testy integracyjne testcontainers                             | 1 sesja         |

**Kolejność jest celowa.** Każda faza zostawia działającą aplikację — możesz zatrzymać się
na dowolnym etapie i mieć coś do pokazania.

---

## 12. Jak korzystać z tych dokumentów w sesji z Opus 4.6

Każda faza w `docs/05-implementation-phases.md` ma sekcję **"Prompt startowy"** —
wystarczy go skopiować. Model dostanie listę plików do utworzenia, kryteria gotowości
oraz wzorce kodu (np. szablon use case'u). Pamięć projektu (`memory/`) ma już zapisane
decyzje, więc nie trzeba ich powtarzać.

**Schemat sesji:**

```
1. "Realizujemy fazę N z docs/05-implementation-phases.md."
2. Opus 4.6 czyta dokumenty fazy + ewentualnie poprzednich faz.
3. Generuje pliki, uruchamia testy.
4. Po zakończeniu — update TASKS.md i ewentualnie memory.
```
