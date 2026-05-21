# Forum Wędkarskie

Projekt akademicki — forum wędkarskie zbudowane jako **modular monolith**
w Clean Architecture, wdrażany na Kubernetes (minikube). Frontend w React + Vite.

> Pełna dokumentacja architektury w katalogu [`docs/`](./docs):
> [`ARCHITECTURE_PLAN.md`](./docs/ARCHITECTURE_PLAN.md) (master plan),
> [`01-clean-architecture.md`](./docs/01-clean-architecture.md) (warstwy + moduły),
> [`02-database-schema.md`](./docs/02-database-schema.md) (schemat DB + Alembic),
> [`03-security.md`](./docs/03-security.md) (JWT + RBAC + ACL),
> [`04-infrastructure.md`](./docs/04-infrastructure.md) (k8s + RabbitMQ + observability),
> [`05-implementation-phases.md`](./docs/05-implementation-phases.md) (roadmapa faz 0–9).

---

## Stack

| Warstwa        | Technologia                                                              |
|----------------|--------------------------------------------------------------------------|
| Backend        | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic               |
| Baza           | PostgreSQL 16 (driver: psycopg3)                                         |
| Auth           | PyJWT (access 15 min + refresh 14 d), Argon2id, RBAC + per-user ACL      |
| Event bus      | RabbitMQ (od fazy 4)                                                     |
| Observability  | structlog (JSON), Prometheus + Grafana (od fazy 7)                       |
| Frontend       | React 18, Vite, React Router 6, pnpm                                     |
| Konteneryzacja | Docker (multi-stage z **`uv`** dla backendu, nginx dla frontendu)        |
| Orkiestracja   | Kubernetes (minikube), Helm 3                                            |

---

## Szybki start (lokalnie)

### Wymagania

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` lub `brew install uv`)
- Docker + docker-compose (do uruchomienia stosu wraz z DB)
- Node 20+ z `corepack` (frontend)

### Backend — sam (bez Dockera)

```bash
cd backend

# 1) Zainstaluj zależności z uv.lock
uv sync

# 2) Skopiuj plik .env (lub ustaw zmienne środowiskowe ręcznie)
cp .env.example .env

# 3) Uruchom PostgreSQL gdziekolwiek (np. docker-compose up -d postgres)

# 4) Zastosuj migracje
uv run alembic upgrade head

# 5) Start serwera deweloperskiego (hot reload)
uv run uvicorn app.main:app --reload
```

Swagger UI: <http://localhost:8000/docs>.

### Pełny stos przez docker-compose

```bash
docker compose up --build
```

Otwiera:
- `http://localhost:8000` — backend (Swagger pod `/docs`)
- `http://localhost:3000` — frontend
- `http://localhost:5050` — pgAdmin (login `admin@forum.pl` / `admin`)

### Kubernetes (minikube)

```bash
# 1) Włącz Ingress NGINX (jednorazowo)
minikube addons enable ingress

# 2) Skieruj Docker do daemonu wewnątrz minikube
eval $(minikube docker-env)

# 3) Zbuduj obrazy LOKALNIE — manifesty mają `imagePullPolicy: Never`
docker build -t forum-wedkarskie-backend:latest  backend/
docker build -t forum-wedkarskie-frontend:latest frontend/

# 4) Zaaplikuj manifesty (kolejność istotna)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/postgres/
kubectl wait --for=condition=ready pod -l app=postgres -n forum-wedkarskie --timeout=120s

kubectl apply -f k8s/backend/configmap.yaml
kubectl apply -f k8s/backend/uploads-pvc.yaml
kubectl delete job backend-migrate -n forum-wedkarskie --ignore-not-found
kubectl apply -f k8s/backend/migration-job.yaml
kubectl wait --for=condition=complete job/backend-migrate -n forum-wedkarskie --timeout=180s

kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/pgadmin/

# 5) Dodaj do /etc/hosts
echo "$(minikube ip) forum.local" | sudo tee -a /etc/hosts
```

Otwórz <http://forum.local>.

---

## Workflow developera

| Cel                          | Polecenie                                       |
|------------------------------|-------------------------------------------------|
| Instalacja / aktualizacja    | `uv sync`                                       |
| Dodanie zależności runtime   | `uv add fastapi-utils`                          |
| Dodanie zależności dev       | `uv add --dev pytest-mock`                      |
| Lint                         | `uv run ruff check .`                           |
| Auto-fix lint                | `uv run ruff check . --fix`                     |
| Format                       | `uv run ruff format .`                          |
| Type-check                   | `uv run mypy app/`                              |
| Test                         | `uv run pytest`                                 |
| Nowa migracja                | `uv run alembic revision --autogenerate -m "…"` |
| Aplikacja migracji           | `uv run alembic upgrade head`                   |
| Rollback ostatniej migracji  | `uv run alembic downgrade -1`                   |
| Bieżąca rewizja              | `uv run alembic current`                        |

---

## Status migracji do v3

Projekt jest w trakcie przebudowy na Clean Architecture + modular monolith.
Roadmapa: [`docs/05-implementation-phases.md`](./docs/05-implementation-phases.md).

- [x] **Faza 0** — Bootstrap (uv, shared/, Alembic, app factory) ✅
- [ ] **Faza 1** — Moduł `identity` (User, Role, Permission, JWT)
- [ ] **Faza 2** — Moduł `content` (Post, Comment, Tag, Category)
- [ ] **Faza 3** — Moduł `files` (generyczny upload)
- [ ] **Faza 4** — RabbitMQ event bus + `notifications` + `audit`
- [ ] **Faza 5** — WebSocket (prosta wersja, sticky cookie)
- [ ] **Faza 6** — Widoki DB + FTS + keyset pagination
- [ ] **Faza 7** — Observability (Prometheus + Grafana)
- [ ] **Faza 8** — k8s polish (NetworkPolicy, CronJob, PDB)
- [ ] **Faza 9** — CI/CD GitHub Actions + E2E

Foldery `backend/app/{core,models,routers,schemas,services}/` są wciąż używane przez
legacy API (kompatybilność wsteczna). Zostaną zastąpione modułami z `app/modules/*`
w fazach 1-3 i wówczas usunięte.

---

## Struktura repo (po fazie 0)

```
.
├── backend/
│   ├── alembic/                 ← migracje (env.py + versions/)
│   ├── alembic.ini
│   ├── pyproject.toml           ← deps + ruff + mypy + pytest config
│   ├── uv.lock                  ← zafiksowane wersje (commit!)
│   ├── .python-version          ← 3.12 (commit!)
│   ├── .env.example             ← szablon zmiennych dla developera
│   ├── Dockerfile               ← multi-stage z uv
│   ├── .dockerignore
│   ├── app/
│   │   ├── main.py              ← app factory create_app()
│   │   ├── config.py
│   │   ├── database.py          ← shim → shared/infrastructure/db
│   │   ├── shared/              ← bazowe abstrakcje (Entity, Repository, ...)
│   │   ├── modules/             ← identity/ content/ files/ notifications/ audit/
│   │   └── {core,models,routers,services,schemas}/  ← LEGACY (do usunięcia)
│   ├── tests/{unit,integration,e2e}/
│   └── uploads/                 ← runtime data, gitignored
├── frontend/                    ← React + Vite + pnpm
├── docs/                        ← dokumentacja architektury (po polsku)
├── k8s/                         ← manifesty kubernetes
│   ├── namespace.yaml
│   ├── backend/                 ← deployment, service, configmap, migration-job, hpa, ...
│   ├── frontend/
│   ├── postgres/                ← + secret.example.yaml (real secret.yaml gitignored)
│   └── pgadmin/
├── docker-compose.yml
├── .gitignore
├── CLAUDE.md                    ← working memory dla AI asystenta
├── TASKS.md                     ← roadmapa zadań
└── README.md
```

---

## Pierwszy commit — checklist czystego repo

Zanim zrobisz `git init && git add . && git commit`, usuń lokalnie:

```bash
# Wyrzuć runtime artifacts (uploads, cache itp.)
rm -rf backend/.venv backend/__pycache__ backend/.mypy_cache backend/.ruff_cache backend/.pytest_cache
rm -rf backend/uploads/* 2>/dev/null   # zostaw .gitkeep
find . -name __pycache__ -type d -prune -exec rm -rf {} +

# Usuń przestarzały requirements.txt (zastąpiony przez uv.lock)
rm backend/requirements.txt

# Usuń mockup dashboard.html z root (jeśli był)
rm -f dashboard.html

# Skopiuj przykładowe sekrety
cp k8s/postgres/secret.example.yaml k8s/postgres/secret.yaml  # i wpisz prawdziwe hasło
cp k8s/pgadmin/secret.example.yaml  k8s/pgadmin/secret.yaml
```

Potem:

```bash
git init
git add .
git status            # sprawdź czy nic wrażliwego się nie wkradło
git commit -m "Initial commit: v3 bootstrap (Clean Architecture skeleton, uv, Alembic)"
git branch -M main
git remote add origin <URL>
git push -u origin main
```

---

## Licencja

MIT (projekt studencki).
