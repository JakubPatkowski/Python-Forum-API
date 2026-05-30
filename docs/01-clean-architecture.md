# 01 — Clean Architecture i moduły

## 1. Cztery warstwy

```
┌───────────────────────────────────────────────────────────────┐
│  Presentation (FastAPI)                                       │
│  - routers/, request/response DTO (Pydantic), DI containers   │
│  - mapery DTO ↔ domain                                        │
│  └──── zależy od ─►  Application                              │
├───────────────────────────────────────────────────────────────┤
│  Application                                                  │
│  - use cases, command/query handlers, application services   │
│  - PORTY: IRepository[T], IUnitOfWork, IEventBus, ...         │
│  └──── zależy od ─►  Domain                                   │
├───────────────────────────────────────────────────────────────┤
│  Domain (czyste reguły biznesowe)                             │
│  - Entity, AggregateRoot, ValueObject, DomainEvent            │
│  - encje konkretne: User, Post, Comment, ...                  │
│  - zero importów z FastAPI / SQLAlchemy / Pydantic            │
├───────────────────────────────────────────────────────────────┤
│  Infrastructure                                               │
│  - SQLAlchemy repository (implementacja portów Application)   │
│  - RabbitMQ event bus, lokalny FileStorage, Argon2Hasher      │
│  - implementuje porty zdefiniowane WYŻEJ                      │
└───────────────────────────────────────────────────────────────┘

Reguła zależności: strzałka tylko do środka.
Domain ← Application ← Infrastructure (impl portów) i Presentation (DI)
```

**Dlaczego nie standardowy podział `models / schemas / services / routers`?**
Bo:
- `models/` (SQLAlchemy) wymusza importowanie ORM-a w "domain" → łamie regułę.
- `services/` zwykle stają się God-objects.
- Brakuje miejsca na **porty** (interfejsy) i **eventy domeny**.

W naszym układzie:
- `models/` istnieje, ale to **infrastructure** — czysta warstwa persystencji.
- `domain/entities/` to oddzielne klasy, niezależne od ORM (dataclassy / klasy domenowe).
- Mapery `domain ↔ infrastructure` siedzą w `infrastructure/persistence/mappers/`.

---

## 2. Drzewo katalogów (cel)

```
backend/
├── alembic/                          # migracje
│   ├── versions/
│   └── env.py
├── alembic.ini
├── pyproject.toml                    # ruff, mypy, pytest config
├── requirements.txt
├── tests/
│   ├── unit/                         # testy domeny, bez DB
│   ├── integration/                  # testcontainers Postgres + RabbitMQ
│   └── e2e/                          # httpx.AsyncClient + uruchomiona aplikacja
└── app/
    ├── main.py                       # FastAPI app factory + DI container
    ├── config.py                     # pydantic-settings
    │
    ├── shared/                       # WSZYSTKO co reużywalne między modułami
    │   ├── domain/
    │   │   ├── entity.py             # Entity, AggregateRoot
    │   │   ├── value_object.py       # ValueObject baza
    │   │   ├── entity_id.py          # EntityId[T], PublicId (UUID v4)
    │   │   ├── events.py             # DomainEvent baza
    │   │   └── errors.py             # DomainError, NotFoundError, ConflictError
    │   ├── application/
    │   │   ├── repository.py         # IRepository[T, ID]
    │   │   ├── unit_of_work.py       # IUnitOfWork
    │   │   ├── event_bus.py          # IEventBus, IEventHandler[E]
    │   │   ├── result.py             # Result[T, E] (Ok/Err)
    │   │   └── use_case.py           # UseCase[Input, Output] baza
    │   ├── infrastructure/
    │   │   ├── db/                   # Base, get_db, session factory
    │   │   ├── eventbus/             # RabbitMQEventBus implementacja
    │   │   ├── auth/                 # PyJWTTokenService, Argon2Hasher
    │   │   ├── storage/              # LocalDiskStorage (port IFileStorage)
    │   │   └── logging/              # structlog setup
    │   └── presentation/
    │       ├── api_response.py       # ApiResponse, ErrorResponse, PaginatedResponse
    │       ├── error_handler.py      # exception_handlers dla DomainError → HTTP
    │       └── deps.py               # Annotated[..., Depends(...)] convenience
    │
    ├── modules/
    │   ├── identity/                      # Identity & Access Management
    │   │   ├── domain/
    │   │   │   ├── user.py           # User (AggregateRoot)
    │   │   │   ├── role.py           # Role (Entity)
    │   │   │   ├── permission.py     # Permission (ValueObject)
    │   │   │   ├── refresh_token.py  # RefreshToken (Entity)
    │   │   │   └── events.py         # UserRegistered, UserBlocked, ...
    │   │   ├── application/
    │   │   │   ├── ports.py          # IUserRepository, IRoleRepository,
    │   │   │   │                     # IPasswordHasher, ITokenService
    │   │   │   ├── use_cases/
    │   │   │   │   ├── register_user.py
    │   │   │   │   ├── login.py
    │   │   │   │   ├── refresh_session.py
    │   │   │   │   ├── logout.py
    │   │   │   │   ├── assign_role.py
    │   │   │   │   └── grant_permission.py
    │   │   │   └── permissions.py    # Permission codes enum + bundles
    │   │   ├── infrastructure/
    │   │   │   ├── orm/              # SQLAlchemy modele
    │   │   │   ├── repositories/     # impl portów
    │   │   │   └── mappers.py        # ORM ↔ Domain
    │   │   └── presentation/
    │   │       ├── routers/
    │   │       │   ├── auth.py
    │   │       │   ├── users.py
    │   │       │   └── roles.py
    │   │       └── dto/              # Pydantic schemas
    │   │
    │   ├── content/                  # Post, Comment, Tag, Category
    │   │   ├── domain/
    │   │   │   ├── post.py
    │   │   │   ├── comment.py        # rekurencyjny path-based
    │   │   │   ├── category.py
    │   │   │   ├── tag.py
    │   │   │   └── events.py
    │   │   ├── application/
    │   │   │   ├── ports.py
    │   │   │   └── use_cases/
    │   │   ├── infrastructure/
    │   │   └── presentation/
    │   │
    │   ├── files/                    # generyczny upload manager
    │   │   ├── domain/
    │   │   │   ├── file.py           # File entity
    │   │   │   └── events.py
    │   │   ├── application/
    │   │   │   ├── ports.py          # IFileRepository, IFileStorage (z shared/)
    │   │   │   └── use_cases/
    │   │   │       ├── upload_file.py
    │   │   │       ├── download_file.py
    │   │   │       └── delete_file.py
    │   │   ├── infrastructure/
    │   │   └── presentation/
    │   │       └── routers/files.py  # /api/v1/files/* (jeden endpoint do wszystkiego)
    │   │
    │   ├── notifications/            # consumer eventów + WS
    │   │   ├── domain/
    │   │   ├── application/
    │   │   │   └── handlers/         # subskrypcje eventów innych modułów
    │   │   ├── infrastructure/
    │   │   └── presentation/
    │   │       └── ws/               # WebSocket endpoint
    │   │
    │   └── audit/                    # consumer wszystkich eventów
    │       ├── domain/
    │       ├── application/
    │       ├── infrastructure/
    │       └── presentation/         # (opcjonalnie) GET /api/v1/admin/audit
    │
    └── admin/                        # Jinja2 SSR panel admina (zostaje, ale używa use case'ów)
        ├── templates/
        ├── static/
        └── routers.py
```

---

## 3. Bazowe abstrakcje (`shared/`)

### 3.1 `EntityId[T]`

```python
# shared/domain/entity_id.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class EntityId(Generic[T]):
    """Strongly-typed identifier for an entity.

    Usage:
        class UserId(EntityId["User"]): ...
        uid = UserId(UUID("..."))
    """
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


# UserId, PostId, CommentId itd. są podklasami EntityId.
class UserId(EntityId["User"]): ...
class PostId(EntityId["Post"]): ...
```

### 3.2 `ValueObject`

```python
# shared/domain/value_object.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ValueObject:
    """Marker base class for Value Objects.

    Value Objects are immutable, equality-by-value, with no identity.
    All subclasses should be @dataclass(frozen=True, slots=True).
    """
```

Przykłady VO: `Email`, `Username`, `Password` (raw, przed hash), `Slug`, `Markdown`, `MimeType`.

### 3.3 `Entity` + `AggregateRoot`

```python
# shared/domain/entity.py
from __future__ import annotations
from typing import Generic, TypeVar
from .entity_id import EntityId
from .events import DomainEvent

ID = TypeVar("ID", bound=EntityId)


class Entity(Generic[ID]):
    """Base for all entities (identity by id)."""
    id: ID

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)


class AggregateRoot(Entity[ID]):
    """Aggregate root — owns child entities, publishes domain events."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events
```

### 3.4 `DomainEvent`

```python
# shared/domain/events.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base for all domain events.

    Concrete events should subclass and add fields, e.g.:
        @dataclass(frozen=True, slots=True)
        class UserRegistered(DomainEvent):
            user_id: UserId
            email: Email
    """
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### 3.5 `IRepository[T, ID]`

```python
# shared/application/repository.py
from typing import Protocol, TypeVar, Generic

T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(Protocol, Generic[T, ID]):
    async def get(self, id_: ID) -> T | None: ...
    async def add(self, entity: T) -> None: ...
    async def remove(self, entity: T) -> None: ...
    async def exists(self, id_: ID) -> bool: ...
```

Każdy moduł rozszerza ten interfejs o własne query metody:

```python
# modules/identity/application/ports.py
class IUserRepository(IRepository[User, UserId], Protocol):
    async def get_by_email(self, email: Email) -> User | None: ...
    async def get_by_username(self, username: Username) -> User | None: ...
    async def list_active(self, limit: int, after: UserId | None) -> list[User]: ...
```

### 3.6 `IUnitOfWork`

```python
# shared/application/unit_of_work.py
from typing import Protocol, AsyncContextManager

class IUnitOfWork(AsyncContextManager["IUnitOfWork"], Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

    # Repositories są właściwościami konkretnej impl UoW
    # (SqlAlchemyUnitOfWork wystawia .users, .posts, .comments, ...)
```

Zastosowanie w use case:

```python
class RegisterUserUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher, bus: IEventBus): ...

    async def execute(self, cmd: RegisterUserCommand) -> Result[UserId, DomainError]:
        async with self.uow as uow:
            if await uow.users.get_by_email(cmd.email):
                return Err(EmailAlreadyTaken(cmd.email))
            user = User.register(cmd.username, cmd.email, self.hasher.hash(cmd.password))
            await uow.users.add(user)
            await uow.commit()
            for event in user.pull_events():
                await self.bus.publish(event)
            return Ok(user.id)
```

### 3.7 `IEventBus`

```python
# shared/application/event_bus.py
from typing import Protocol, Callable, Awaitable, TypeVar
from shared.domain.events import DomainEvent

E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], Awaitable[None]]


class IEventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None: ...
```

Dwie implementacje:
- `InMemoryEventBus` — do testów i prostszych use case'ów (w obrębie procesu).
- `RabbitMQEventBus` — produkcyjna (`aio-pika`), publikuje na exchange `forum.events`,
  każdy moduł-konsument ma własną kolejkę `forum.{module}.events`.

### 3.8 `Result[T, E]`

```python
# shared/application/result.py
from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E


Result = Union[Ok[T], Err[E]]
```

Use case zwraca `Result`, presentation layer mapuje do HTTP (200 / 4xx / 5xx) w jednym miejscu.

### 3.9 `UseCase` baza

```python
# shared/application/use_case.py
from typing import Protocol, TypeVar

I = TypeVar("I", contravariant=True)
O = TypeVar("O", covariant=True)


class UseCase(Protocol[I, O]):
    async def execute(self, input_: I) -> O: ...
```

### 3.10 `ApiResponse` / `ErrorResponse`

```python
# shared/presentation/api_response.py
from typing import Generic, TypeVar, Literal
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Successful API response wrapper."""
    data: T
    meta: dict[str, str] | None = None


class ErrorDetail(BaseModel):
    code: str            # 'EMAIL_ALREADY_TAKEN'
    message: str         # human-readable
    field: str | None = None  # for validation errors


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total: int | None = None  # opcjonalnie, drogie do liczenia
```

Globalny exception handler w `shared/presentation/error_handler.py` mapuje:
- `NotFoundError` → 404 + ErrorResponse
- `ConflictError` → 409
- `PermissionDeniedError` → 403
- `ValidationError` (z domeny) → 422
- inne → 500 (z `request_id` z `X-Request-ID` header)

---

## 4. Moduły — szczegółowo

### 4.1 `identity` (Identity & Access Management)

**Agregaty:**
- `User` (AggregateRoot) — `id: UserId`, `username`, `email`, `password_hash`, `is_active`,
  `roles: list[Role]`, `direct_permissions: set[Permission]`.
- `Role` (Entity) — `id: RoleId`, `name`, `permissions: set[Permission]`.
- `Permission` (ValueObject) — `code: str` (np. `"post.delete.any"`).
- `RefreshToken` (Entity) — `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`, `replaced_by`.

**Eventy:**
- `UserRegistered`, `UserBlocked`, `UserUnblocked`, `UserRoleChanged`,
  `RefreshTokenIssued`, `RefreshTokenReuseDetected`.

**Use case'y:**
- `RegisterUserUseCase`, `LoginUseCase`, `RefreshSessionUseCase`, `LogoutUseCase`,
  `AssignRoleUseCase`, `GrantPermissionUseCase`, `RevokePermissionUseCase`.

**API:**
- `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout`
- `GET /api/v1/users/me`, `PATCH /api/v1/users/me`
- `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}/role`,
  `PATCH /api/v1/admin/users/{id}/permissions`

### 4.2 `content`

**Agregaty:**
- `Post` (AR) — `id: PostId`, `author_id`, `category_id`, `title`, `slug`, `content`,
  `content_format`, `tags: list[Tag]`, `created_at`.
- `Comment` (AR) — `id: CommentId`, `post_id`, `parent_id: CommentId | None`, `author_id`,
  `content`, `depth: int`, `path: str` (np. `"00001.00005.00012"`), `is_deleted: bool`.
- `Category`, `Tag` — proste encje.

**Komentarze nieskończenie zagnieżdżone:**
Materializujemy `path` jako string (zero-padded fragmenty id), żeby `WHERE path LIKE 'parent_path%'`
dawał subtree w `O(log n)` z indeksem B-Tree. Alternatywa: PostgreSQL `ltree` (lepsze, ale wymaga extension).
Decyzja: **path string** — dla portability i prostoty.

**Eventy:**
- `PostCreated`, `PostUpdated`, `PostDeleted`,
- `CommentAdded`, `CommentDeleted`.

**API:**
- `GET /api/v1/posts?cursor=&category=&tag=` (keyset pagination)
- `POST /api/v1/posts`, `GET /api/v1/posts/{id}`, `PUT /api/v1/posts/{id}`, `DELETE ...`
- `GET /api/v1/posts/{post_id}/comments?tree=true`
- `POST /api/v1/comments`, `PUT /api/v1/comments/{id}`, `DELETE ...`
- `GET /api/v1/categories`, `POST /api/v1/categories` (moderator+)
- `GET /api/v1/tags`

### 4.3 `files` — generyczny manager plików

**Encja `File`:**
- `id: FileId`, `uploader_id`, `storage_key`, `original_name`, `content_type`, `size_bytes`,
  `sha256`, `owner_type: Literal["user_avatar", "post", "comment", null]`, `owner_id`,
  `created_at`.

**Generyczność:** jeden zestaw endpointów obsługuje wszystkie use case'y:
- `POST /api/v1/files?owner_type=post&owner_id=...` — upload, dodaje metadata, zwraca `File`.
- `POST /api/v1/files?owner_type=user_avatar` (owner_id = current_user.id, opcjonalnie pomijany).
- `GET /api/v1/files/{file_id}` — download (autoryzacja: publiczne / per-owner).
- `GET /api/v1/files/{file_id}/info` — metadata.
- `DELETE /api/v1/files/{file_id}` — uploader lub moderator+.
- `GET /api/v1/users/{user_id}/avatar` → 302 redirect do `/api/v1/files/{avatar_file_id}`.

**Embed w komentarzach/postach:** w treści markdown `![alt](file:UUID)` — frontend zamienia
przy renderowaniu na `<img src="/api/v1/files/UUID">`.

**Storage adapter:**
```python
# shared/application/file_storage.py  (port)
class IFileStorage(Protocol):
    async def save(self, content: AsyncIterable[bytes], storage_key: str) -> None: ...
    async def open(self, storage_key: str) -> AsyncIterable[bytes]: ...
    async def delete(self, storage_key: str) -> None: ...
    async def exists(self, storage_key: str) -> bool: ...
```

Implementacje: `LocalDiskStorage` (PVC w k8s). Trywialne dodanie `S3Storage` później.

### 4.4 `notifications`

**Consumer eventów:** subskrybuje `PostCreated`, `CommentAdded`, `UserRoleChanged`.
Tworzy obiekty `Notification` w DB (opcjonalnie) i broadcastuje przez WS.

**WebSocket:**
- `GET /ws/notifications` (z `Authorization: Bearer ...` w query lub w pierwszym message).
- Replika trzyma `dict[UserId, set[WebSocket]]`.
- W "prostej wersji" (wybrany wariant) — sticky session na poziomie Ingress.

### 4.5 `audit`

**Consumer:** subskrybuje wszystkie eventy (`#` routing key). Zapisuje do tabeli `audit_log`.
Endpoint admina: `GET /api/v1/admin/audit?actor_id=&type=&from=&to=` z paginacją.

---

## 5. Komunikacja między modułami

**Zasada:** moduły nigdy nie importują prywatnych klas innego modułu. Dozwolone są:

1. **Eventy domeny** (przez RabbitMQ lub `InMemoryEventBus`).
2. **Publiczne porty** — interfejs wystawiony w `modules/<m>/__init__.py`.

Przykład: `notifications` nie importuje `User` z `identity.domain.user`. Zamiast tego, w evencie
`PostCreated` jest `author_id: UserId` (publiczny) i ewentualnie `author_username` (denormalizacja).

Egzekwowanie: opcjonalnie `import-linter` z kontraktami w `pyproject.toml`:

```toml
[tool.importlinter]
root_packages = ["app"]

[[tool.importlinter.contracts]]
name = "Modules don't import each other's internals"
type = "forbidden"
source_modules = ["app.modules.content"]
forbidden_modules = [
    "app.modules.identity.domain",
    "app.modules.identity.application",
    "app.modules.identity.infrastructure",
]
```

---

## 6. Dependency Injection

FastAPI ma natywne DI. W `app/main.py` lub `app/container.py` rejestrujemy fabryki:

```python
# app/container.py
from functools import lru_cache
from app.config import settings
from app.shared.infrastructure.eventbus.rabbitmq import RabbitMQEventBus
from app.modules.identity.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
# ...

@lru_cache
def get_event_bus() -> IEventBus:
    return RabbitMQEventBus(settings.RABBITMQ_URL)

# UoW jest per-request, NIE @lru_cache
def get_uow() -> IUnitOfWork:
    return SqlAlchemyUnitOfWork(SessionLocal)

# Use case per-request
def get_register_user_uc() -> RegisterUserUseCase:
    return RegisterUserUseCase(get_uow(), Argon2Hasher(), get_event_bus())
```

W routerze:

```python
@router.post("/register", status_code=201)
async def register(
    body: RegisterUserRequest,
    uc: Annotated[RegisterUserUseCase, Depends(get_register_user_uc)],
) -> ApiResponse[UserResponse]:
    result = await uc.execute(body.to_command())
    return present(result, mapper=UserResponse.from_domain)
```

---

## 7. Co z obecnym kodem?

Stan obecny (`backend/app/{models,schemas,services,routers}`) **NIE jest stracony** —
posłuży jako referencja. Migracja będzie inkrementalna, moduł po module
(patrz `docs/05-implementation-phases.md`).

Krok 0 fazy 0 — przygotowanie struktury i przeniesienie istniejącego kodu:
- `models/*.py` → `modules/<m>/infrastructure/orm/*.py`
- `schemas/*.py` → `modules/<m>/presentation/dto/*.py`
- `services/*.py` → tymczasowo `modules/<m>/application/use_cases/`, potem refaktor
- `routers/*.py` → `modules/<m>/presentation/routers/*.py`

Po przeniesieniu — fazy 1+ wprowadzają **prawdziwą** warstwę domain.
