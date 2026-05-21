# 02 — Schemat bazy danych, migracje Alembic, widoki

## 1. Konwencje

- **PK wewnętrzne:** `bigserial` (kolumna `id`). Nigdy nie wystawiane w API.
- **Klucze publiczne:** `uuid` (UUIDv7, sortowalne czasowo) w kolumnie `public_id`,
  `unique not null default gen_random_uuid()` (lub funkcja `uuid_generate_v7()` z extension).
  *Pragmatyzm:* jeśli `uuid_generate_v7()` nie jest dostępne, używamy `gen_random_uuid()` (v4)
  i sortujemy po `created_at`.
- **Timestampy:** `timestamptz`, domyślnie `now()`, dla `updated_at` używamy triggera lub
  ustawiamy w aplikacji (SQLAlchemy `onupdate=...`).
- **Soft delete:** kolumna `is_deleted boolean default false`. Dla komentarzy obowiązkowo —
  drzewo nie może mieć dziur.
- **Wszystkie ENUMy:** Postgres `CREATE TYPE`, nie text + check (mniej błędów, łatwiej rozszerzać).
- **Indeksy:** każdy FK → indeks. Dodatkowo: partial indexes (`WHERE is_deleted = false`),
  GIN dla `tsvector` i `tags`.
- **Komentarze SQL:** `COMMENT ON COLUMN ...` dla wszystkich nieoczywistych kolumn.

---

## 2. Schemat — moduł `identity`

```sql
-- ENUMs
CREATE TYPE user_status AS ENUM ('active', 'blocked', 'pending_verification');
CREATE TYPE token_status AS ENUM ('active', 'rotated', 'revoked');

-- users
CREATE TABLE users (
    id              bigserial PRIMARY KEY,
    public_id       uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    username        varchar(50)  NOT NULL UNIQUE,
    email           varchar(255) NOT NULL UNIQUE,
    password_hash   varchar(255) NOT NULL,           -- Argon2 encoded
    status          user_status  NOT NULL DEFAULT 'active',
    avatar_file_id  bigint NULL REFERENCES files(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_email_lower ON users (lower(email));
CREATE INDEX idx_users_username_lower ON users (lower(username));

-- roles
CREATE TABLE roles (
    id          bigserial PRIMARY KEY,
    name        varchar(50) NOT NULL UNIQUE,         -- 'admin', 'moderator', 'user', custom...
    description text
);

-- permissions (kody dziedzinowe, np. 'post.delete.any')
CREATE TABLE permissions (
    id          bigserial PRIMARY KEY,
    code        varchar(100) NOT NULL UNIQUE,         -- 'post.create', 'comment.delete.any', ...
    description text
);

-- M:N: rola → uprawnienia (bundle)
CREATE TABLE role_permissions (
    role_id       bigint NOT NULL REFERENCES roles(id)       ON DELETE CASCADE,
    permission_id bigint NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- M:N: użytkownik → role
CREATE TABLE user_roles (
    user_id  bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id  bigint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at timestamptz NOT NULL DEFAULT now(),
    granted_by bigint NULL REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, role_id)
);

-- Per-user override (granted = true: dodaje uprawnienie, false: cofa pomimo roli)
CREATE TABLE user_permissions (
    user_id       bigint NOT NULL REFERENCES users(id)       ON DELETE CASCADE,
    permission_id bigint NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted       boolean NOT NULL,                   -- true=allow, false=deny
    granted_at    timestamptz NOT NULL DEFAULT now(),
    granted_by    bigint NULL REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, permission_id)
);

-- refresh tokens (whitelist + rotation chain)
CREATE TABLE refresh_tokens (
    id           bigserial PRIMARY KEY,
    public_id    uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    user_id      bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   varchar(128) NOT NULL UNIQUE,        -- sha256 hex of raw token
    status       token_status NOT NULL DEFAULT 'active',
    issued_at    timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz NULL,
    replaced_by  bigint NULL REFERENCES refresh_tokens(id) ON DELETE SET NULL,
    user_agent   text NULL,
    ip_address   inet NULL
);
CREATE INDEX idx_refresh_user_status ON refresh_tokens (user_id, status);
CREATE INDEX idx_refresh_expires_active ON refresh_tokens (expires_at)
    WHERE status = 'active';
```

**Seed ról i uprawnień** (w migracji Alembic `0002_seed_identity.py`):

```python
PERMISSIONS = [
    # posts
    "post.read", "post.create", "post.update.own", "post.update.any",
    "post.delete.own", "post.delete.any",
    # comments
    "comment.read", "comment.create", "comment.update.own", "comment.update.any",
    "comment.delete.own", "comment.delete.any",
    # files
    "file.upload", "file.download", "file.delete.own", "file.delete.any",
    # categories / tags
    "category.manage", "tag.manage",
    # admin
    "user.read.any", "user.manage", "role.manage", "audit.read",
]

ROLES = {
    "user":      ["post.read", "post.create", "post.update.own", "post.delete.own",
                  "comment.read", "comment.create", "comment.update.own", "comment.delete.own",
                  "file.upload", "file.download", "file.delete.own"],
    "moderator": [...same plus...
                  "post.update.any", "post.delete.any",
                  "comment.update.any", "comment.delete.any",
                  "file.delete.any", "category.manage", "tag.manage"],
    "admin":     [...moderator plus...
                  "user.read.any", "user.manage", "role.manage", "audit.read"],
}
```

---

## 3. Schemat — moduł `content`

```sql
CREATE TYPE content_format AS ENUM ('plain', 'markdown');

CREATE TABLE categories (
    id          bigserial PRIMARY KEY,
    public_id   uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    name        varchar(100) NOT NULL UNIQUE,
    slug        varchar(120) NOT NULL UNIQUE,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tags (
    id     bigserial PRIMARY KEY,
    name   varchar(50)  NOT NULL UNIQUE,
    slug   varchar(60)  NOT NULL UNIQUE
);

CREATE TABLE posts (
    id              bigserial PRIMARY KEY,
    public_id       uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    author_id       bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id     bigint NULL  REFERENCES categories(id) ON DELETE SET NULL,
    title           varchar(200) NOT NULL,
    slug            varchar(220) NOT NULL,
    content         text NOT NULL,
    content_format  content_format NOT NULL DEFAULT 'markdown',
    -- Full-text search vector (PL/EN). Aktualizowany triggerem.
    search_tsv      tsvector,
    is_deleted      boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_posts_author_slug ON posts (author_id, slug);
CREATE INDEX idx_posts_category_created ON posts (category_id, created_at DESC)
    WHERE is_deleted = false;
CREATE INDEX idx_posts_search_tsv ON posts USING GIN (search_tsv);

-- Trigger pod tsvector
CREATE FUNCTION posts_tsv_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_tsv :=
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_posts_tsv BEFORE INSERT OR UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION posts_tsv_trigger();

CREATE TABLE post_tags (
    post_id bigint NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id  bigint NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);
CREATE INDEX idx_post_tags_tag ON post_tags (tag_id);

CREATE TABLE comments (
    id            bigserial PRIMARY KEY,
    public_id     uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    post_id       bigint NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    parent_id     bigint NULL REFERENCES comments(id) ON DELETE CASCADE,
    author_id     bigint NULL REFERENCES users(id) ON DELETE SET NULL,  -- soft-detach po usunięciu usera
    content       text NOT NULL,
    content_format content_format NOT NULL DEFAULT 'markdown',
    depth         int NOT NULL DEFAULT 0,
    -- Materializowana ścieżka dla szybkich subtree query.
    -- Format: zero-padded 8-cyfrowe ID rozdzielone kropką, np. '00000001.00000005.00000012'
    path          varchar(200) NOT NULL,
    is_deleted    boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_comments_post_path ON comments (post_id, path);
CREATE INDEX idx_comments_parent ON comments (parent_id);
-- Subtree queries:  WHERE path LIKE '00000001.00000005%' AND post_id = ?
```

**Dlaczego materializowana ścieżka (`path`) zamiast tylko `parent_id`?**
- `parent_id` wystarczy do zapisu i validacji, ale rekursywne `WITH RECURSIVE` na każdym listingu drzewa
  jest drogie przy dużym ruchu.
- `path` + indeks B-Tree na `(post_id, path)` daje:
  - subtree: `WHERE path LIKE '<parent_path>%'` w czasie logarytmicznym
  - sortowanie chronologiczne w drzewie: `ORDER BY path`
  - poziom: `depth` jest cached, ale można też zliczać kropki w `path`.

**Maksymalna głębokość:** brak hard limit'u w DB. W warstwie domeny dodajemy walidator
`MAX_COMMENT_DEPTH` (configurable, domyślnie 8). Powyżej — error `CommentDepthExceeded`.

---

## 4. Schemat — moduł `files`

```sql
CREATE TYPE file_owner_type AS ENUM ('user_avatar', 'post', 'comment', 'standalone');

CREATE TABLE files (
    id              bigserial PRIMARY KEY,
    public_id       uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    uploader_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    storage_key     varchar(255) NOT NULL UNIQUE,    -- nazwa pliku na dysku (uuid + ext)
    original_name   varchar(255) NOT NULL,
    content_type    varchar(100) NOT NULL,
    size_bytes      bigint NOT NULL CHECK (size_bytes > 0),
    sha256          char(64) NOT NULL,
    owner_type      file_owner_type NOT NULL DEFAULT 'standalone',
    owner_post_id   bigint NULL REFERENCES posts(id)    ON DELETE CASCADE,
    owner_comment_id bigint NULL REFERENCES comments(id) ON DELETE CASCADE,
    owner_user_id   bigint NULL REFERENCES users(id)    ON DELETE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT now(),

    -- XOR ownership: dokładnie 0 lub 1 owner_X_id w zależności od owner_type
    CONSTRAINT files_owner_check CHECK (
        (CASE WHEN owner_post_id    IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN owner_comment_id IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN owner_user_id    IS NOT NULL THEN 1 ELSE 0 END)
        <= 1
    ),
    CONSTRAINT files_owner_type_match CHECK (
        (owner_type = 'post'        AND owner_post_id    IS NOT NULL) OR
        (owner_type = 'comment'     AND owner_comment_id IS NOT NULL) OR
        (owner_type = 'user_avatar' AND owner_user_id    IS NOT NULL) OR
        (owner_type = 'standalone'  AND owner_post_id IS NULL
                                    AND owner_comment_id IS NULL
                                    AND owner_user_id IS NULL)
    )
);
CREATE INDEX idx_files_owner_post    ON files (owner_post_id)    WHERE owner_post_id    IS NOT NULL;
CREATE INDEX idx_files_owner_comment ON files (owner_comment_id) WHERE owner_comment_id IS NOT NULL;
CREATE INDEX idx_files_owner_user    ON files (owner_user_id)    WHERE owner_user_id    IS NOT NULL;
CREATE INDEX idx_files_sha256        ON files (sha256);  -- deduplication / lookup
```

**Dedup po `sha256`:** opcjonalne — endpoint upload może wykryć duplikat i zwrócić istniejący `File`
z owner == nowy owner (czyli plik fizycznie jeden, metadane wiele). Decyzja: **nie w MVP** —
prościej trzymać jeden rekord per upload. Dedup może być fazą 6.

---

## 5. Schemat — moduł `audit`

```sql
CREATE TABLE audit_log (
    id              bigserial PRIMARY KEY,
    event_id        uuid NOT NULL UNIQUE,
    occurred_at     timestamptz NOT NULL,
    event_type      varchar(100) NOT NULL,           -- 'UserRegistered', 'PostDeleted', ...
    actor_user_id   bigint NULL REFERENCES users(id) ON DELETE SET NULL,
    target_type     varchar(50) NULL,                -- 'post', 'comment', 'user', ...
    target_public_id uuid NULL,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_event_type ON audit_log (event_type);
CREATE INDEX idx_audit_actor      ON audit_log (actor_user_id, occurred_at DESC);
CREATE INDEX idx_audit_target     ON audit_log (target_type, target_public_id);
```

---

## 6. Widoki SQL

### 6.1 `v_user_effective_permissions`

Efektywne uprawnienia użytkownika = `UNION` (uprawnienia z ról) `UNION` (granted=true z user_permissions)
`MINUS` (granted=false z user_permissions).

```sql
CREATE OR REPLACE VIEW v_user_effective_permissions AS
WITH role_perms AS (
    SELECT ur.user_id, p.code
    FROM user_roles ur
    JOIN role_permissions rp ON rp.role_id = ur.role_id
    JOIN permissions p ON p.id = rp.permission_id
),
direct_grants AS (
    SELECT up.user_id, p.code
    FROM user_permissions up
    JOIN permissions p ON p.id = up.permission_id
    WHERE up.granted = true
),
direct_denies AS (
    SELECT up.user_id, p.code
    FROM user_permissions up
    JOIN permissions p ON p.id = up.permission_id
    WHERE up.granted = false
)
SELECT DISTINCT u.user_id, u.code
FROM (
    SELECT * FROM role_perms
    UNION
    SELECT * FROM direct_grants
) u
WHERE NOT EXISTS (
    SELECT 1 FROM direct_denies d
    WHERE d.user_id = u.user_id AND d.code = u.code
);
```

Aplikacja: `SELECT code FROM v_user_effective_permissions WHERE user_id = ?` przy logowaniu →
osadzamy w JWT access tokenie jako `permissions: [...]`.

### 6.2 `v_posts_with_stats`

```sql
CREATE OR REPLACE VIEW v_posts_with_stats AS
SELECT
    p.id, p.public_id, p.title, p.slug, p.content, p.content_format,
    p.author_id, p.category_id, p.created_at, p.updated_at,
    u.username AS author_username,
    u.public_id AS author_public_id,
    c.name AS category_name,
    c.slug AS category_slug,
    (SELECT COUNT(*) FROM comments cm
        WHERE cm.post_id = p.id AND cm.is_deleted = false) AS comment_count,
    (SELECT COUNT(*) FROM files f
        WHERE f.owner_post_id = p.id) AS attachment_count
FROM posts p
JOIN users u ON u.id = p.author_id
LEFT JOIN categories c ON c.id = p.category_id
WHERE p.is_deleted = false;
```

Lista postów = jeden SELECT z `v_posts_with_stats ORDER BY created_at DESC LIMIT 20`.

### 6.3 `v_comment_tree_lite`

```sql
CREATE OR REPLACE VIEW v_comment_tree_lite AS
SELECT
    c.id, c.public_id, c.post_id, c.parent_id,
    c.depth, c.path, c.is_deleted,
    c.content, c.content_format,
    c.created_at, c.updated_at,
    c.author_id, u.username AS author_username
FROM comments c
LEFT JOIN users u ON u.id = c.author_id;
```

Listing drzewa = `SELECT ... FROM v_comment_tree_lite WHERE post_id = ? ORDER BY path` —
sortowanie po `path` daje **już** kolejność DFS.

### 6.4 `v_top_posters_30d`

```sql
CREATE OR REPLACE VIEW v_top_posters_30d AS
SELECT
    u.id, u.public_id, u.username,
    COUNT(p.id) AS posts_count
FROM users u
JOIN posts p ON p.author_id = u.id
WHERE p.created_at >= now() - interval '30 days'
  AND p.is_deleted = false
GROUP BY u.id, u.public_id, u.username
ORDER BY posts_count DESC
LIMIT 50;
```

### 6.5 Materializowane widoki — kiedy?

Dla studenckiego projektu zwykłe widoki wystarczą. Jeśli chcesz pokazać dodatkową
optymalizację — dodaj `CREATE MATERIALIZED VIEW v_post_stats_mv ... WITH DATA` i
`REFRESH MATERIALIZED VIEW CONCURRENTLY` w cronie/task scheduler.

---

## 7. Alembic — setup

### 7.1 Instalacja i konfiguracja

```bash
pip install alembic
cd backend
alembic init alembic
```

Edycja `alembic.ini` — `sqlalchemy.url` zostaje pusty, czytamy z env w `env.py`:

```python
# backend/alembic/env.py — kluczowe linie
from app.config import settings
from app.shared.infrastructure.db.base import Base

# importujemy wszystkie ORM modele (rejestracja w Base.metadata)
from app.modules.identity.infrastructure.orm import *  # noqa
from app.modules.content.infrastructure.orm import *  # noqa
from app.modules.files.infrastructure.orm import *  # noqa
from app.modules.audit.infrastructure.orm import *  # noqa

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
```

### 7.2 Pierwsza migracja

```bash
# Po zdefiniowaniu wszystkich ORM modeli:
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 7.3 Konwencja nazw migracji

`<revision_id>_<slug>.py`. Slug po angielsku, opisujący zmianę:
- `0001_initial_schema`
- `0002_seed_roles_and_permissions`
- `0003_add_search_tsv_to_posts`
- `0004_add_comment_path_index`

### 7.4 Stałe nazwy ograniczeń (naming convention)

W `app/shared/infrastructure/db/base.py`:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Base = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))
```

Dzięki temu autogeneracja Alembica daje stabilne, deterministyczne nazwy → autogenerate
nie wykrywa fałszywych "zmian" przy każdej migracji.

### 7.5 Migration Job w k8s

Zamiast init-containera (race condition przy `replicas: N`), używamy `Job`:

```yaml
# k8s/backend/migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: backend-migrate
  namespace: forum-wedkarskie
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: forum-wedkarskie-backend:latest
          imagePullPolicy: Never
          command: ["alembic", "upgrade", "head"]
          envFrom:
            - configMapRef:
                name: backend-config
            - secretRef:
                name: backend-secrets
```

Workflow deployu:
1. `kubectl apply -f k8s/postgres/`
2. `kubectl apply -f k8s/backend/migration-job.yaml` → `kubectl wait --for=condition=complete job/backend-migrate`
3. `kubectl apply -f k8s/backend/deployment.yaml`

Można zautomatyzować w skrypcie `scripts/deploy.sh`.

### 7.6 Backfill data migrations

Każda migracja zmieniająca schemat z istniejącymi danymi musi mieć część **data migration**:

```python
# 0005_add_user_status_enum.py
def upgrade() -> None:
    op.execute("CREATE TYPE user_status AS ENUM ('active', 'blocked', 'pending_verification')")
    op.add_column('users', sa.Column('status', sa.Enum('active', 'blocked', 'pending_verification',
                                                       name='user_status'), nullable=True))
    op.execute("UPDATE users SET status = CASE WHEN is_active THEN 'active' ELSE 'blocked' END")
    op.alter_column('users', 'status', nullable=False)
    op.drop_column('users', 'is_active')
```

---

## 8. Indeksy — checklist

Każdy FK → indeks. Dodatkowo:

| Tabela          | Indeks                                                  | Powód                                 |
|-----------------|---------------------------------------------------------|---------------------------------------|
| users           | `(lower(email))`, `(lower(username))`                   | Case-insensitive lookup przy logowaniu|
| posts           | `(category_id, created_at DESC) WHERE NOT is_deleted`   | Listing kategorii                     |
| posts           | `GIN(search_tsv)`                                       | FTS                                   |
| comments        | `(post_id, path)`                                       | Subtree queries                       |
| refresh_tokens  | `(user_id, status)`                                     | Logout wszystkich sesji usera         |
| refresh_tokens  | `(expires_at) WHERE status='active'`                    | Cleanup job                            |
| files           | `(owner_post_id) WHERE NOT NULL` (i analogiczne)        | Listing załączników posta             |
| audit_log       | `(event_type)`, `(actor_user_id, occurred_at DESC)`     | Filtry w panelu admina                |

---

## 9. Cleanup jobs

- **Wygasłe refresh tokens:** cron co 24h — `DELETE FROM refresh_tokens WHERE expires_at < now()`.
- **Osierocone pliki:** plik na dysku bez wiersza w `files` → cron co 24h porównuje listing PVC z DB.
  *Pragmatyzm:* w MVP pomijamy, tylko logujemy ostrzeżenie.
- **Audit log retention:** jeśli rośnie za szybko — partition by month + `DROP TABLE audit_log_2024_01` po 12 mies.
  Pominięte w MVP.

---

## 10. Pytania otwarte

1. **`uuid_generate_v7()`** — nie ma natywnie w Postgres 16. Trzeba albo:
   - generować w aplikacji (Python `uuid_extensions` lub własna implementacja),
   - użyć `gen_random_uuid()` (v4) — prościej, ale tracimy sort-by-id ≈ sort-by-time.
   **Rekomendacja:** zacząć od v4, zoptymalizować jeśli wystąpią problemy.

2. **Czy `comments.author_id` ma być `ON DELETE CASCADE` czy `SET NULL`?**
   Wybrałem `SET NULL` — usunięty user nie powinien kasować historii dyskusji.
   Dodajemy fallback "Deleted user" w prezentacji.

3. **`tsvector` PL/EN** — `simple` configuration jest językowo neutralna, bez stemming.
   Dla polskiego można zainstalować `pg_dictionary_polish` (osobny extension).
   **Rekomendacja:** zacząć od `simple`, ulepszyć jeśli będzie czas.
