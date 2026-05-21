# 04 — Infrastruktura: Kubernetes, RabbitMQ, observability

## 1. Topologia w klastrze (minikube)

```
namespace: forum-wedkarskie

deployments:
  - frontend            (replicas: 2,  image: forum-wedkarskie-frontend:latest)
  - backend             (replicas: 2,  HPA 2-6, image: forum-wedkarskie-backend:latest)
  - postgres            (replicas: 1,  PVC postgres-pvc 5Gi)
  - rabbitmq            (replicas: 1,  PVC rabbitmq-pvc 2Gi, management UI :15672)
  - pgadmin             (replicas: 1)

statefulset (alternatywnie dla DB i RabbitMQ - dla edukacji można użyć Deployment):
  - postgres (StatefulSet bardziej kanoniczne ale Deployment z PVC działa)

services:
  - frontend-service           (ClusterIP :80)
  - backend-service            (ClusterIP :8000)
  - postgres-service           (ClusterIP :5432, headless)
  - rabbitmq-service           (ClusterIP :5672 + :15672 management)
  - pgadmin-service            (ClusterIP :80, NodePort opcjonalnie)

ingress (NGINX):
  - host: forum.local
    paths:
      /               -> frontend-service:80
      /api/v1         -> backend-service:8000
      /ws             -> backend-service:8000  (sticky cookie affinity)

jobs:
  - backend-migrate           (alembic upgrade head)
  - cleanup-refresh-tokens    (CronJob @daily)

helm releases:
  - kube-prometheus-stack     (Prometheus + Grafana + AlertManager + node-exporter)

config:
  - backend-config (ConfigMap):  DATABASE_URL, RABBITMQ_URL, UPLOAD_DIR, app config
  - backend-secrets (Secret):    SECRET_KEY, DB password, RABBITMQ password
  - rabbitmq-secret (Secret):    erlang cookie, default user/password
  - postgres-secret (Secret):    POSTGRES_PASSWORD
```

---

## 2. Struktura `k8s/`

```
k8s/
├── namespace.yaml
├── ingress.yaml                            # jeden Ingress dla domeny forum.local
│
├── postgres/
│   ├── pvc.yaml
│   ├── secret.example.yaml
│   ├── deployment.yaml                     # albo statefulset.yaml
│   └── service.yaml                        # headless dla StatefulSet
│
├── rabbitmq/
│   ├── pvc.yaml
│   ├── secret.example.yaml
│   ├── deployment.yaml
│   └── service.yaml
│
├── backend/
│   ├── configmap.yaml
│   ├── secret.example.yaml
│   ├── uploads-pvc.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml
│   ├── migration-job.yaml
│   └── cleanup-cronjob.yaml
│
├── frontend/
│   ├── deployment.yaml
│   └── service.yaml
│
├── pgadmin/
│   ├── secret.example.yaml
│   ├── deployment.yaml
│   └── service.yaml
│
└── monitoring/
    ├── README.md                           # instrukcja helm install
    ├── prometheus-values.yaml              # values dla kube-prometheus-stack
    └── servicemonitor-backend.yaml         # scrape /metrics z backendu
```

---

## 3. Backend Deployment + HPA

```yaml
# k8s/backend/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: forum-wedkarskie
  labels: { app: backend }
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  selector:
    matchLabels: { app: backend }
  template:
    metadata:
      labels: { app: backend }
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: "/metrics"
        prometheus.io/port: "8000"
    spec:
      containers:
        - name: backend
          image: forum-wedkarskie-backend:latest
          imagePullPolicy: Never
          ports:
            - { name: http, containerPort: 8000 }
          envFrom:
            - configMapRef: { name: backend-config }
            - secretRef:    { name: backend-secrets }
          volumeMounts:
            - { name: uploads, mountPath: /app/uploads }
          startupProbe:
            httpGet: { path: /health/live, port: 8000 }
            failureThreshold: 30   # ~5 min na boot
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /health/ready, port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /health/live, port: 8000 }
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests: { cpu: "200m", memory: "256Mi" }
            limits:   { cpu: "1000m", memory: "512Mi" }
      volumes:
        - name: uploads
          persistentVolumeClaim:
            claimName: backend-uploads-pvc
```

```yaml
# k8s/backend/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: forum-wedkarskie
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
    - type: Resource
      resource:
        name: memory
        target: { type: Utilization, averageUtilization: 80 }
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

**Health endpoints:**
- `/health/live` — czy proces żyje (zwraca 200 zawsze ile aplikacja się boots).
- `/health/ready` — czy gotowy do ruchu (sprawdza DB SELECT 1, RabbitMQ connect).

---

## 4. Ingress (sticky sessions dla WS)

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: forum-ingress
  namespace: forum-wedkarskie
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"     # długie WS
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    # Sticky sessions dla WS (cookie-based affinity)
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "forum-ws-affinity"
    nginx.ingress.kubernetes.io/session-cookie-path: "/ws"
spec:
  ingressClassName: nginx
  rules:
    - host: forum.local
      http:
        paths:
          - path: /api/v1
            pathType: Prefix
            backend: { service: { name: backend-service,  port: { number: 8000 } } }
          - path: /ws
            pathType: Prefix
            backend: { service: { name: backend-service,  port: { number: 8000 } } }
          - path: /
            pathType: Prefix
            backend: { service: { name: frontend-service, port: { number: 80   } } }
```

W minikube włączamy ingress:
```bash
minikube addons enable ingress
echo "$(minikube ip) forum.local" | sudo tee -a /etc/hosts
```

---

## 5. PostgreSQL

```yaml
# k8s/postgres/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: forum-wedkarskie
spec:
  accessModes: [ReadWriteOnce]
  resources: { requests: { storage: 5Gi } }
```

```yaml
# k8s/postgres/deployment.yaml — kluczowy fragment
spec:
  replicas: 1
  strategy: { type: Recreate }
  template:
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          env:
            - { name: POSTGRES_DB,    value: forum_wedkarskie }
            - { name: POSTGRES_USER,  value: postgres }
            - name: POSTGRES_PASSWORD
              valueFrom: { secretKeyRef: { name: postgres-secret, key: POSTGRES_PASSWORD } }
            - { name: PGDATA, value: /var/lib/postgresql/data/pgdata }
          ports: [ { containerPort: 5432 } ]
          volumeMounts:
            - { name: data, mountPath: /var/lib/postgresql/data }
          readinessProbe:
            exec: { command: ["pg_isready", "-U", "postgres"] }
          resources:
            requests: { cpu: "100m", memory: "256Mi" }
            limits:   { cpu: "1000m", memory: "1Gi" }
      volumes:
        - name: data
          persistentVolumeClaim: { claimName: postgres-pvc }
```

---

## 6. RabbitMQ

Decyzja: zacząć od ręcznego manifesta (jeden plik, zrozumiały), opcjonalnie migracja do chartu Bitnami.

```yaml
# k8s/rabbitmq/deployment.yaml — kluczowy fragment
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: rabbitmq
          image: rabbitmq:3.13-management-alpine
          ports:
            - { name: amqp, containerPort: 5672 }
            - { name: mgmt, containerPort: 15672 }
          env:
            - { name: RABBITMQ_DEFAULT_USER, value: forum }
            - name: RABBITMQ_DEFAULT_PASS
              valueFrom: { secretKeyRef: { name: rabbitmq-secret, key: RABBITMQ_PASSWORD } }
          volumeMounts:
            - { name: data, mountPath: /var/lib/rabbitmq }
          readinessProbe:
            exec: { command: ["rabbitmq-diagnostics", "-q", "ping"] }
            periodSeconds: 30
          resources:
            requests: { cpu: "100m", memory: "256Mi" }
            limits:   { cpu: "500m", memory: "512Mi" }
      volumes:
        - name: data
          persistentVolumeClaim: { claimName: rabbitmq-pvc }
```

```yaml
# k8s/rabbitmq/service.yaml
apiVersion: v1
kind: Service
metadata: { name: rabbitmq-service, namespace: forum-wedkarskie }
spec:
  selector: { app: rabbitmq }
  ports:
    - { name: amqp, port: 5672,  targetPort: 5672 }
    - { name: mgmt, port: 15672, targetPort: 15672 }
```

Management UI: `kubectl port-forward svc/rabbitmq-service 15672:15672` → `http://localhost:15672`.

---

## 7. Event Bus — topologia kolejek

```
Exchange (topic):  forum.events
                   durable=true, auto_delete=false

Routing key:       <module>.<EventName>
                   "identity.UserRegistered"
                   "content.PostCreated"
                   "content.CommentAdded"
                   "files.FileUploaded"

Queues (durable, per-consumer):
  audit.queue           bindings:  "#"                  (wszystkie eventy)
  notifications.queue   bindings:  "content.*", "identity.*"  (filtruje co istotne)
  search.queue (przyszłość) bindings: "content.*"

Dead Letter Exchange: forum.events.dlx (topic)
  - kazda queue ma x-dead-letter-exchange = forum.events.dlx
  - DLQ per moduł: audit.dlq, notifications.dlq
```

**Implementacja w Pythonie (`aio-pika`):**

```python
# app/shared/infrastructure/eventbus/rabbitmq.py
import aio_pika, json
from aio_pika.abc import AbstractConnection
from typing import Type
from app.shared.domain.events import DomainEvent

EXCHANGE_NAME = "forum.events"


class RabbitMQEventBus:
    def __init__(self, url: str) -> None:
        self._url = url
        self._conn: AbstractConnection | None = None
        self._channel = None
        self._exchange = None
        self._handlers: dict[Type[DomainEvent], list] = {}

    async def connect(self) -> None:
        self._conn = await aio_pika.connect_robust(self._url)
        self._channel = await self._conn.channel()
        await self._channel.set_qos(prefetch_count=10)
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def publish(self, event: DomainEvent) -> None:
        routing_key = f"{event_module(event)}.{type(event).__name__}"
        body = json.dumps(event_to_dict(event)).encode()
        msg = aio_pika.Message(body, content_type="application/json",
                               delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                               headers={"event_id": str(event.event_id)})
        await self._exchange.publish(msg, routing_key=routing_key)

    async def consume(self, queue_name: str, bindings: list[str],
                      handler) -> None:
        queue = await self._channel.declare_queue(
            queue_name, durable=True,
            arguments={"x-dead-letter-exchange": f"{EXCHANGE_NAME}.dlx"})
        for rk in bindings:
            await queue.bind(self._exchange, routing_key=rk)
        await queue.consume(self._make_handler(handler))
```

**Outbox pattern (opcjonalny, ale wart wzmianki):**
Trzymaj tabelę `domain_events_outbox` w tej samej transakcji co zmianę agregatu.
Osobny worker czyta nieopublikowane eventy i wysyła do RabbitMQ.
Gwarancja: nigdy nie publikujemy eventu o zmianie, której nie ma w DB, i nigdy nie zapisujemy
zmiany bez eventu. Implementacja w fazie 4 — opcjonalna, ale dobrze zaprezentować.

---

## 8. WebSocket — prosta wersja

**Topologia:**
- Endpoint `/ws/notifications` w backendzie.
- Replika trzyma `dict[UserId, set[WebSocket]]` (in-memory).
- Notyfikacja powstaje z:
  1. Event handler w `notifications` module (consumer RabbitMQ) → tworzy `Notification`.
  2. Jeśli `notifications.NotificationCreated` jest dla user X, broadcastujemy do WS sockets X **w tej replice**.

**Ograniczenie wybrane przez Ciebie:** jeśli notyfikacja powstała w replice A, a klient WS jest na replice B,
to dopiero przy następnym fetch'u user zobaczy notyfikację. Akceptowalne dla MVP.

**Implementacja:**

```python
# app/modules/notifications/presentation/ws/notifications.py
from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Annotated

class WSManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = {}

    async def register(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.setdefault(user_id, set()).add(ws)

    async def unregister(self, user_id: str, ws: WebSocket) -> None:
        self.connections.get(user_id, set()).discard(ws)

    async def broadcast_to(self, user_id: str, payload: dict) -> None:
        for ws in list(self.connections.get(user_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                await self.unregister(user_id, ws)

ws_manager = WSManager()  # singleton per replika


@router.websocket("/ws/notifications")
async def ws_notifications(
    ws: WebSocket,
    user: Annotated[User, Depends(get_current_user_ws)],
) -> None:
    await ws_manager.register(user.public_id, ws)
    try:
        while True:
            await ws.receive_text()  # heartbeat — ignorujemy treść
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.unregister(user.public_id, ws)
```

**Sticky sessions w Ingress** już skonfigurowane (sekcja 4). Cookie `forum-ws-affinity` po pierwszym
żądaniu przypina klienta do repliki na czas trwania WS.

---

## 9. Observability — Prometheus + Grafana

### 9.1 Instalacja przez Helm

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring

helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values k8s/monitoring/prometheus-values.yaml
```

`prometheus-values.yaml` — głównie hasła Grafany, pojemność PVC, retencja:

```yaml
grafana:
  adminPassword: "changeme"
  service: { type: ClusterIP }
prometheus:
  prometheusSpec:
    retention: "7d"
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources: { requests: { storage: 5Gi } }
```

### 9.2 Backend `/metrics`

```python
# app/main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator(
    excluded_handlers=["/health/live", "/health/ready", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics")
```

Domyślne metryki: `http_requests_total`, `http_request_duration_seconds`, `http_requests_inprogress`.

**Custom metryki dla domeny** (rozsiane po use case'ach):

```python
# app/shared/infrastructure/metrics.py
from prometheus_client import Counter, Histogram

POSTS_CREATED = Counter("forum_posts_created_total", "Total posts created")
COMMENTS_CREATED = Counter("forum_comments_created_total", "Total comments created",
                           ["depth_bucket"])
LOGIN_FAILURES = Counter("forum_login_failures_total", "Login failures", ["reason"])
EVENT_PUBLISHED = Counter("forum_events_published_total", "Domain events published", ["event_type"])
USE_CASE_DURATION = Histogram("forum_use_case_seconds", "Use case execution time", ["use_case"])
```

### 9.3 ServiceMonitor

```yaml
# k8s/monitoring/servicemonitor-backend.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: backend-monitor
  namespace: forum-wedkarskie
  labels: { release: kube-prometheus }   # ważne! taki label, jaki ma operator
spec:
  selector: { matchLabels: { app: backend } }
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

### 9.4 Grafana dashboards

Importować lub stworzyć:
- **FastAPI Overview**: requests/s, p50/p95/p99 latency, error rate (5xx), HPA replicas.
- **Domain Activity**: posts/s, comments/s, signups/s, login failures/s.
- **Database**: PG connections, query duration p95 (z postgres-exporter — opcjonalnie).
- **RabbitMQ**: queue depths, publish/consume rate (rabbitmq-exporter — opcjonalnie).

W repozytorium jako JSON: `k8s/monitoring/dashboards/forum-overview.json`. Wczytujemy
sidecar dashboardów Grafany przez ConfigMap.

### 9.5 Logi

`structlog` JSON do stdout — Kubernetes podnosi z `kubectl logs`. Dla projektu studenckiego wystarczy.

```python
# app/shared/infrastructure/logging/setup.py
import structlog, logging, sys

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )
```

---

## 10. NetworkPolicy (opcjonalne, ale punkt na obronie)

```yaml
# k8s/backend/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-egress
  namespace: forum-wedkarskie
spec:
  podSelector: { matchLabels: { app: backend } }
  policyTypes: [Egress]
  egress:
    - to:
        - podSelector: { matchLabels: { app: postgres } }
      ports: [ { protocol: TCP, port: 5432 } ]
    - to:
        - podSelector: { matchLabels: { app: rabbitmq } }
      ports: [ { protocol: TCP, port: 5672 } ]
    - to: [ { namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } } } ]
      ports: [ { protocol: UDP, port: 53 } ]   # DNS
```

Analogicznie `Ingress` policy blokująca dostęp do postgres-a spoza `app: backend`.

---

## 11. Optymalizacja obrazów

### 11.1 Backend Dockerfile (multi-stage)

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

FROM base AS builder
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links /wheels /wheels/*.whl && rm -rf /wheels

# Non-root user
RUN useradd -u 1000 -m -s /bin/bash app
USER app
COPY --chown=app:app . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 11.2 Frontend Dockerfile (multi-stage)

```dockerfile
# frontend/Dockerfile (już prawdopodobnie masz)
FROM node:20-alpine AS build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

---

## 12. Deploy workflow (skrypt)

```bash
# scripts/deploy.sh
#!/usr/bin/env bash
set -euo pipefail

# 1. Switch docker to minikube
eval $(minikube docker-env)

# 2. Build images
docker build -t forum-wedkarskie-backend:latest  backend/
docker build -t forum-wedkarskie-frontend:latest frontend/

# 3. Apply manifests (idempotent)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/rabbitmq/
kubectl apply -f k8s/backend/configmap.yaml
kubectl apply -f k8s/backend/secret.yaml
kubectl apply -f k8s/backend/uploads-pvc.yaml

# 4. Wait for postgres
kubectl wait --for=condition=ready pod -l app=postgres -n forum-wedkarskie --timeout=120s

# 5. Run migration job (delete previous, then apply)
kubectl delete job backend-migrate -n forum-wedkarskie --ignore-not-found
kubectl apply -f k8s/backend/migration-job.yaml
kubectl wait --for=condition=complete job/backend-migrate -n forum-wedkarskie --timeout=180s

# 6. Rest of backend + frontend
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/pgadmin/
kubectl apply -f k8s/ingress.yaml

# 7. Rollout
kubectl rollout restart deployment/backend  -n forum-wedkarskie
kubectl rollout status  deployment/backend  -n forum-wedkarskie
kubectl rollout status  deployment/frontend -n forum-wedkarskie

echo "Done. Open http://forum.local"
```

---

## 13. Co dalej (przyszłe ulepszenia)

- **Redis** dla cache + rate limit shared state + opcjonalnie WS backplane.
- **Argo CD / Flux** zamiast `kubectl apply` — GitOps.
- **Skaffold** zamiast skryptu — `skaffold dev` z auto-rebuild.
- **OpenTelemetry** — distributed tracing (Jaeger).
- **PodDisruptionBudget** dla backendu, żeby drain node nie zamknął wszystkich replik naraz.
- **Backups Postgres** — `pg_dump` przez CronJob → PVC.
