# Forum Wędkarskie - jak projekt jest zbudowany i jak go uruchomić lokalnie

Ten dokument opisuje aktualny stan projektu na podstawie istniejących plików repozytorium
(README, CLAUDE.md, Dockerfile, docker-compose, manifesty k8s, konfiguracja backend/front).

## 1. Jak projekt jest zbudowany

Projekt jest monorepo z podziałem na backend, frontend i infrastrukturę:

- `backend/` - API w FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2, Alembic, JWT, RBAC.
- `frontend/` - React 18 + Vite, budowany przez pnpm i serwowany przez Nginx w kontenerze.
- `k8s/` - manifesty Kubernetes dla `postgres`, `backend`, `frontend`, `pgadmin`.
- `docs/` - dokumentacja architektury i planu migracji.

### Backend (FastAPI)

Najwazniejsze elementy:

- App factory w `backend/app/main.py` (`create_app()`), plus modułowy `app` dla `uvicorn app.main:app`.
- Routery:
  - nowe endpointy `api/v1` dla identity,
  - legacy endpointy `api/*` dla kategorii/postow/komentarzy/zalacznikow,
  - panel admina SSR pod `/admin`.
- Health checki:
  - `/health` (legacy),
  - `/health/live`,
  - `/health/ready`.
- Schemat bazy jest zarzadzany przez Alembic (bez `create_all` w runtime).

### Frontend (React + Vite + Nginx)

- W dewelopmencie Vite dziala na porcie `3000` i proxyfikuje `/api` do `http://localhost:8000`.
- W kontenerze produkcyjnym Nginx serwuje statyczny build z `dist/`.
- Nginx przekazuje `/api/*` do `backend-service:8000`, wiec frontend i backend lacza sie wewnatrz klastra po DNS K8s.

### Baza i pliki

- PostgreSQL 16 (`postgres:16-alpine`).
- Trwale dane DB przez PVC `postgres-pvc`.
- Zalaczniki backendu przez osobny PVC `backend-uploads-pvc` montowany pod `/app/uploads`.

## 2. Jak dziala Kubernetes (Minikube) w tym projekcie

Namespace:

- Wszystko dziala w namespace `forum-wedkarskie`.

Obrazy:

- Manifesty backend i frontend maja `imagePullPolicy: Never`.
- To oznacza, ze w Minikube obrazy musza byc zbudowane lokalnie w docker daemonie Minikube
  (`forum-wedkarskie-backend:latest` i `forum-wedkarskie-frontend:latest`).

Uslugi:

- `postgres-service` - ClusterIP: baza dostepna tylko wewnatrz klastra.
- `backend-service` - ClusterIP: API dostepne wewnatrz klastra.
- `frontend-service` - NodePort `30080`: punkt wejscia dla UI.
- `pgadmin-service` - NodePort `30050`: pgAdmin do podgladu bazy.

Migracje DB:

- Migracje sa odpalane jako osobny Job `backend-migrate` (`alembic upgrade head`).
- To zapobiega konfliktom, ktore wystepowalyby przy migracji wykonywanej w kazdym podzie backendu.

Config i sekrety:

- `k8s/backend/configmap.yaml` trzyma konfiguracje backendu.
- `k8s/postgres/secret.yaml` oraz `k8s/pgadmin/secret.yaml` trzymaja dane logowania.
- W repo sa tez pliki `secret.example.yaml` jako szablony.

## 3. Jak uruchomic projekt lokalnie

Ponizej trzy najwygodniejsze scenariusze.

## 3A. Najszybciej: Docker Compose

Uruchamia jednoczesnie: Postgres, backend, frontend i pgAdmin.

```bash
docker compose up --build
```

Po starcie:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- pgAdmin: `http://localhost:5050`

Uwagi:

- Backend w compose uruchamia: `alembic upgrade head` przed startem Uvicorna.
- Mount `./backend:/app` daje hot-reload backendu.

## 3B. Lokalny development bez Dockera (backend + frontend)

Wymagania:

- Python 3.12+
- `uv`
- Node 20+ z `corepack`
- lokalny Postgres

### Backend

```bash
cd backend
uv sync
```

Skopiuj env:

```bash
cp .env.example .env
```

Odpal migracje i serwer:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
corepack enable
pnpm install
pnpm dev
```

Po starcie:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## 3C. Kubernetes na Minikube (lokalny klaster)

Wymagania:

- Minikube
- kubectl
- Docker

### Krok 1: start klastra

```bash
minikube start
```

Jesli `kubectl apply` zwraca blad typu `failed to download openapi` albo `connection refused`,
to zwykle oznacza, ze Minikube nie dziala albo `kubectl` wskazuje na zly context. Sprawdz:

```bash
minikube status
kubectl config current-context
```

W razie potrzeby ustaw kontekst na Minikube:

```bash
kubectl config use-context minikube
```

### Krok 2: przelaczenie Dockera na Minikube

Linux/macOS:

```bash
eval $(minikube docker-env)
```

Windows PowerShell:

```powershell
minikube -p minikube docker-env --shell powershell | Invoke-Expression
```

### Krok 3: build obrazow

```bash
docker build -t forum-wedkarskie-backend:latest backend/
docker build -t forum-wedkarskie-frontend:latest frontend/
```

### Krok 4: upewnij sie, ze sekrety istnieja

Jesli nie masz lokalnych plikow `secret.yaml`, utworz je z szablonow:

```bash
cp k8s/postgres/secret.example.yaml k8s/postgres/secret.yaml
cp k8s/pgadmin/secret.example.yaml k8s/pgadmin/secret.yaml
```

Nastepnie wpisz realne hasla w obu plikach.

### Krok 5: deploy manifestow (zalecana kolejnosc)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/postgres/
kubectl wait --for=condition=ready pod -l app=postgres -n forum-wedkarskie --timeout=120s

kubectl apply -f k8s/backend/configmap.yaml
kubectl apply -f k8s/backend/uploads-pvc.yaml
kubectl delete job backend-migrate -n forum-wedkarskie --ignore-not-found
kubectl apply -f k8s/backend/migration-job.yaml
kubectl wait --for=condition=complete job/backend-migrate -n forum-wedkarskie --timeout=180s

kubectl apply -f k8s/backend/deployment.yaml
kubectl apply -f k8s/backend/service.yaml
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/pgadmin/
```

### Krok 6: dostep do uslug

Najprosciej:

```bash
minikube service frontend-service -n forum-wedkarskie --url
minikube service pgadmin-service -n forum-wedkarskie --url
```

Alternatywnie przez `minikube ip` + NodePort:

- Frontend: `http://<MINIKUBE_IP>:30080`
- pgAdmin: `http://<MINIKUBE_IP>:30050`

## 4. Szybka diagnostyka

Status zasobow:

```bash
kubectl get all -n forum-wedkarskie
kubectl get pvc -n forum-wedkarskie
kubectl get jobs -n forum-wedkarskie
```

Logi:

```bash
kubectl logs deployment/backend -n forum-wedkarskie
kubectl logs deployment/frontend -n forum-wedkarskie
kubectl logs deployment/postgres -n forum-wedkarskie
kubectl logs job/backend-migrate -n forum-wedkarskie
```

Najczestsze problemy:

- `ImagePullBackOff` dla backend/frontendu:
  - obrazy nie zostaly zbudowane w docker daemonie Minikube,
  - rozwiazanie: ponownie wykonaj krok z `docker-env` i `docker build`.
- Backend nie wstaje po deploy:
  - nieudane migracje Alembic,
  - rozwiazanie: sprawdz logi joba `backend-migrate`.
- Problem z niezgodna stara baza (lokalny dev):
  - czasem trzeba usunac PVC Postgresa i postawic DB od nowa.

## 5. Podsumowanie przeplywu

1. Uzytkownik otwiera frontend.
2. Frontend wysyla zapytania do `/api`.
3. Nginx (frontend) przekazuje je do `backend-service`.
4. Backend korzysta z `postgres-service` i zapisuje pliki do PVC `backend-uploads-pvc`.
5. W Kubernetes migracje sa uruchamiane jednorazowo przez Job `backend-migrate` przed backendem.
