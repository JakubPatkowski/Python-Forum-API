# 13 — Kubernetes: professional setup, how it works, and run instructions

> **What this document is.** A self-contained, English runbook for the
> production-style Kubernetes setup added in this session: security hardening,
> autoscaling, monitoring (Prometheus + Grafana + Loki), ingress, network
> policies, and load testing. It explains **what was built**, **how each part
> works**, and **exactly how to run and demo it**.
>
> Audience: someone new to Kubernetes. Every command is copy-paste ready
> (Windows PowerShell, minikube).
>
> Date: 2026-06-04 · Related: `docs/11` (audit), `docs/12` (Cursor's status +
> manual runbook). This document supersedes the K8s parts of `docs/06`.

---

## 1. TL;DR — the three commands

From the repository root, in PowerShell:

```powershell
# 1) Build images + deploy the whole app to minikube (app, DB, MinIO, HPA, ingress)
.\scripts\deploy.ps1 -Build -Monitoring

# 2) (deploy.ps1 -Monitoring already did this) install Grafana/Prometheus/Loki
#    — or run it separately later:
.\scripts\install-monitoring.ps1

# 3) Generate traffic and watch the backend autoscale 2 -> 6 pods
.\scripts\run-load-test.ps1 -Watch
```

Then add one line to your hosts file (the script prints the exact IP):

```
<minikube ip>   forum.local
```

Everything else below is detail: how it works, how to reach each panel for the
class demo, the security model, and troubleshooting.

---

## 2. What was built this session

| Area | What | Files |
|------|------|-------|
| **Security hardening** | `securityContext` on every workload (non-root where the image allows, drop capabilities, seccomp, read-only root FS for the backend), Pod Security Admission labels on the namespace | `k8s/*/deployment.yaml`, `k8s/namespace.yaml` |
| **Secrets** | JWT `SECRET_KEY` moved out of the ConfigMap into a generated Secret; helper that creates a strong random key | `k8s/backend/configmap.yaml`, `scripts/generate-secrets.ps1` |
| **Health probes** | Backend liveness → `/health/live` (process only), readiness → `/health/ready` (real `SELECT 1` on the DB, returns 503 when DB is down); `pg_isready` probes for Postgres | `k8s/backend/deployment.yaml`, `k8s/postgres/deployment.yaml` |
| **Autoscaling** | HorizontalPodAutoscaler for backend (2–6, CPU 70%) and frontend (2–4); PodDisruptionBudgets | `k8s/backend/hpa.yaml`, `k8s/backend/pdb.yaml`, `k8s/frontend/hpa.yaml` |
| **Monitoring** | kube-prometheus-stack (Prometheus + Grafana + Alertmanager + node/pod metrics), Loki + Promtail for logs, a `ServiceMonitor` to scrape the app, a custom Grafana dashboard, example alert rules | `k8s/monitoring/*`, `scripts/install-monitoring.ps1` |
| **Ingress** | Single host `forum.local` for the SPA + Swagger; optional `grafana.local` | `k8s/ingress/*` |
| **Network policies** | Safe default (DB reachable only from the backend) + optional full lockdown set | `k8s/network-policies/*` |
| **Load testing** | k6 script + in-cluster Job + runner script | `load/*`, `scripts/run-load-test.ps1` |
| **Resource limits** | requests/limits on every container (also the basis for HPA) | all deployments |
| **Reproducible images** | pinned MinIO / mc image tags instead of `:latest` | `docker-compose.yml`, `k8s/minio/*` |
| **Tighter CORS** | explicit methods/headers instead of `*` | `backend/app/main.py` |
| **Deploy automation** | one staged script that does addons, secrets, DB, MinIO, migrations, app, scaling, ingress | `scripts/deploy.ps1` |

---

## 3. Architecture — how the pieces fit

```
                         ┌─────────────────────── minikube node ───────────────────────┐
                         │                                                              │
  Browser ──http──► Ingress (forum.local) ──► frontend (nginx, 2–4 pods, HPA)          │
  DataGrip ─────────────────────────────────┐         │  proxies /api /docs /static    │
                                             │         ▼                                │
                                             │   backend (FastAPI, 2–6 pods, HPA)       │
                                             │     │           │                        │
                                             │     ▼           ▼                        │
                                             │  postgres     MinIO (S3 + console)       │
                                             │  (NetworkPolicy: only backend may reach) │
                                             │                                          │
   monitoring namespace:                     │   Prometheus ──scrape /metrics──► backend│
   Grafana ◄── Prometheus (metrics)          │   Promtail ──tail stdout──► Loki ◄─ all  │
   Grafana ◄── Loki (logs)                   │                                          │
                         └──────────────────────────────────────────────────────────────┘
```

**Request path:** browser → ingress (`forum.local`) → frontend pod (nginx) →
the SPA is served directly, and `/api`, `/docs`, `/redoc`, `/static`, `/admin`
are reverse-proxied to `backend-service` → backend pods. `backend-service` is a
ClusterIP, so it **round-robins across all backend replicas** — that is why the
load test spreads traffic across pods.

**Why a Service in front of the pods:** pods are disposable and get new IPs; the
Service is a stable virtual IP + DNS name (`backend-service:8000`) that always
points at the current healthy pods (the ones passing the readiness probe).

**Scaling loop:** metrics-server reports each pod's CPU → the HPA compares it to
the 70% target → it changes the Deployment's replica count → new pods register
with the Service automatically.

**Monitoring loop:** the backend exposes `/metrics`; a `ServiceMonitor` tells
Prometheus to scrape it every 15s; Grafana queries Prometheus for metrics and
Loki for logs, both on one dashboard.

---

## 4. File map (what each new/changed file does)

```
k8s/
  namespace.yaml                         # labels + Pod Security Admission (baseline enforce)
  backend/
    deployment.yaml                      # hardened, probes live/ready, secret wired, named port
    service.yaml                         # named "http" port (ServiceMonitor scrapes it)
    configmap.yaml                       # app config; SECRET_KEY removed (now a Secret)
    hpa.yaml                             # autoscale 2–6 on CPU 70% / mem 80%
    pdb.yaml                             # keep >=1 backend pod during disruptions
    migration-job.yaml                   # alembic upgrade head (runs once per deploy)
    cleanup-cronjob.yaml                 # daily orphan-file cleanup
    uploads-pvc.yaml                     # persistent uploads
  frontend/
    deployment.yaml                      # hardened, probes, resources
    configmap.yaml                       # nginx: proxies /api, /docs, /redoc, /static
    hpa.yaml                             # frontend HPA (2–4) + PDB
  postgres/  minio/                      # hardened deployments, pinned image tags, probes
  ingress/
    ingress-app.yaml                     # forum.local -> frontend (SPA + Swagger)
    ingress-monitoring.yaml              # grafana.local (optional)
  monitoring/
    values-kube-prometheus-stack.yaml    # Helm values (Prometheus + Grafana + alerts)
    values-loki-stack.yaml               # Helm values (Loki + Promtail)
    servicemonitor-backend.yaml          # scrape backend /metrics
    grafana-dashboard-forum.yaml         # "Forum Overview" dashboard (auto-imported)
    prometheus-rules.yaml                # example alerts
  network-policies/
    postgres-allow-backend.yaml          # SAFE DEFAULT: DB only from backend
    full-lockdown/                       # OPTIONAL: default-deny + per-app allows (needs Calico)
load/
  k6-load-test.js                        # the load scenario
  k6-job.yaml                            # runs k6 in-cluster
scripts/
  deploy.ps1                             # full staged deploy (rewritten)
  generate-secrets.ps1                   # create/rotate secrets
  install-monitoring.ps1                 # Helm install monitoring + app objects
  run-load-test.ps1                      # upload script + run k6 Job + tail logs
  scaling-demo.ps1                       # live HPA + pods + kubectl top
  portforward.ps1                        # all port-forwards (no pgAdmin)
```

---

## 5. Prerequisites (install once)

You need these on Windows (the tools that aren't already there):

- **Docker Desktop** (image build engine)
- **minikube** — `winget install Kubernetes.minikube`
- **kubectl** — `winget install Kubernetes.kubectl`
- **Helm 3** — `winget install Helm.Helm` (only needed for monitoring)

Verify:

```powershell
docker version
minikube version
kubectl version --client
helm version
```

> If `helm` is missing you can still deploy the app; you only need it for the
> monitoring stack (`install-monitoring.ps1`).

---

## 6. Deploy — the easy path (recommended)

```powershell
# from the repo root
.\scripts\deploy.ps1 -Build -Monitoring
```

What this does, in order (it is a teaching script — read its `[1/9]…[9/9]`
output):

1. Start minikube (if stopped) and enable the `ingress` + `metrics-server` addons.
2. Point Docker at the minikube daemon so images are built **inside** the node
   (minikube can't pull your local `:latest` images otherwise → that's why the
   deployments use `imagePullPolicy: Never`).
3. Build the backend and frontend images.
4. Create the namespace and the three Secrets (random `SECRET_KEY`).
5. Deploy PostgreSQL, wait until ready.
6. Deploy MinIO, wait, create the `forum-files` bucket.
7. Render the real minikube IP into `MINIO_PUBLIC_ENDPOINT` (so presigned file
   URLs work from the browser) and run the Alembic migration Job.
8. Deploy backend + frontend + HPAs + PDBs + the safe NetworkPolicy + the ingress.
9. (`-Monitoring`) install Prometheus/Grafana/Loki via Helm.

When it finishes, it prints the **hosts line** to add (as Administrator) to
`C:\Windows\System32\drivers\etc\hosts`:

```
<minikube ip>   forum.local
```

Re-deploying after a code change:

```powershell
.\scripts\deploy.ps1 -Build      # rebuild images + roll out, keep data
.\scripts\deploy.ps1 -Clean -Build   # also wipe DB/MinIO/uploads volumes
```

> **NetworkPolicy enforcement note.** The default minikube CNI does **not**
> enforce NetworkPolicies — they are accepted but ignored. To actually enforce
> them (and demo "the DB rejects everyone but the backend"), recreate the
> cluster with Calico:
> ```powershell
> minikube delete
> minikube start --cpus=4 --memory=8192 --cni=calico
> ```
> Then re-run `deploy.ps1`. Add `-Lockdown` to also apply the full lockdown set.

---

## 7. Deploy — the manual path (to learn what the script does)

If you want to run it by hand, see `docs/12` section 4, or follow this condensed
version:

```powershell
minikube start --cpus=4 --memory=8192
minikube addons enable ingress metrics-server
minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t forum-wedkarskie-backend:latest backend/
docker build -t forum-wedkarskie-frontend:latest frontend/

kubectl apply -f k8s/namespace.yaml
.\scripts\generate-secrets.ps1

kubectl apply -f k8s/postgres/ ; kubectl wait --for=condition=ready pod -l app=postgres -n forum-wedkarskie --timeout=120s
kubectl apply -f k8s/minio/deployment.yaml -f k8s/minio/service.yaml -f k8s/minio/pvc.yaml
kubectl wait --for=condition=ready pod -l app=minio -n forum-wedkarskie --timeout=120s
kubectl apply -f k8s/minio/create-bucket-job.yaml

# render MinIO IP, then migrate
$ip = (minikube ip).Trim()
(Get-Content k8s/backend/configmap.yaml -Raw) -replace '<minikube-ip>', $ip | kubectl apply -f -
kubectl apply -f k8s/backend/uploads-pvc.yaml
kubectl apply -f k8s/backend/migration-job.yaml
kubectl wait --for=condition=complete job/backend-migrate -n forum-wedkarskie --timeout=180s

kubectl apply -f k8s/backend/deployment.yaml -f k8s/backend/service.yaml -f k8s/backend/hpa.yaml -f k8s/backend/pdb.yaml -f k8s/backend/cleanup-cronjob.yaml
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/network-policies/postgres-allow-backend.yaml
kubectl apply -f k8s/ingress/ingress-app.yaml
.\scripts\install-monitoring.ps1
```

---

## 8. The class demo — how to reach every panel

After `deploy.ps1`, open a terminal and run `.\scripts\portforward.ps1`
(keeps all forwards alive), or use the per-service commands below.

### 8.1 Frontend + Swagger
- **Ingress (best for demo):** http://forum.local and http://forum.local/docs
- **Port-forward fallback:** `kubectl port-forward svc/frontend-service 3000:80 -n forum-wedkarskie` → http://localhost:3000 ; Swagger via `svc/backend-service 8000:8000` → http://localhost:8000/docs

### 8.2 Database via DataGrip
```powershell
kubectl port-forward svc/postgres-service 5432:5432 -n forum-wedkarskie
```
DataGrip → PostgreSQL → host `localhost`, port `5432`, database `forum_wedkarskie`, user `postgres`, password `postgres`.

### 8.3 MinIO
- Console: `http://<minikube ip>:30901` (or forward `svc/minio-service 9001:9001`) → login `minioadmin` / `minioadmin`
- Bucket `forum-files` holds all uploaded objects + thumbnails.

### 8.4 Grafana — metrics **and** logs
```powershell
kubectl port-forward svc/monitoring-grafana 3001:80 -n monitoring
```
- http://localhost:3001 — login `admin` / `admin`
- **Dashboards → "Forum Overview"**: request rate, 5xx error rate, p95 latency,
  backend replica count (current vs desired, the HPA story), per-pod CPU/memory,
  and a **live Loki logs panel**.
- **Explore → Loki** for ad-hoc log queries, e.g.:
  ```logql
  {namespace="forum-wedkarskie", pod=~"backend-.*"}
  ```
- Check the app is being scraped: **Connections/Status → Targets** (Prometheus)
  → `backend` should be **UP**.

### 8.5 Kubernetes dashboard + per-pod resource usage
```powershell
minikube dashboard          # opens the web UI: Deployments, Pods, HPA, Events
kubectl get pods -n forum-wedkarskie -o wide
kubectl top pods -n forum-wedkarskie        # live CPU/memory per pod
kubectl get hpa -n forum-wedkarskie
```

### 8.6 App metrics raw (no Grafana)
`http://localhost:8000/metrics` (after forwarding `backend-service`).

---

## 9. Scaling demo (the headline for the K8s course)

Two terminals:

```powershell
# Terminal 1 — live view
.\scripts\scaling-demo.ps1

# Terminal 2 — generate load (k6 runs inside the cluster, no local install)
.\scripts\run-load-test.ps1
```

What you should see and narrate:

1. The load test ramps virtual users (30 → 80 → 150) hitting public GET
   endpoints through `backend-service`.
2. CPU per backend pod rises above the 70% target.
3. The HPA increases `desired` replicas; new backend pods appear and become
   Ready; `backend-service` starts load-balancing across all of them.
4. On the Grafana dashboard, "Backend replicas: current vs desired" steps up,
   request rate climbs, and CPU spreads across pods.
5. After the test ends, replicas scale back down slowly (180s stabilization, so
   a brief dip doesn't flap pods).

Run locally instead (if you have k6 installed):
```powershell
k6 run -e BASE_URL=http://forum.local load/k6-load-test.js
```

---

## 10. Security model (what to say on the defense)

- **Secrets, not ConfigMaps.** The JWT signing key is a generated 128-hex-char
  Secret (`backend-secrets`), created by `generate-secrets.ps1`. It is never
  committed. This closes the audit's #1 finding (key was in a committed ConfigMap).
- **Least-privilege containers.** Backend and the Jobs run **non-root (uid 1000)**,
  drop **all Linux capabilities**, set `allowPrivilegeEscalation: false`,
  `seccompProfile: RuntimeDefault`, and the backend uses a **read-only root
  filesystem** (only `/app/uploads` (PVC) and `/tmp` (emptyDir) are writable).
- **Why Postgres/MinIO/nginx aren't forced non-root.** Their official images
  must start as root to fix file ownership (Postgres/MinIO) or bind port 80
  (nginx), then drop privileges themselves. Forcing `runAsNonRoot` would break
  them, so they get the safe subset (seccomp, no privilege escalation). The
  upgrade paths (non-root MinIO on a fresh volume, `nginx-unprivileged`) are
  noted in the manifests.
- **Pod Security Admission.** The namespace enforces the `baseline` profile and
  warns/audits against `restricted`, so violations are surfaced without blocking
  the demo.
- **Network segmentation.** `postgres-allow-backend` makes the database reachable
  only from backend pods. The optional `full-lockdown/` set adds a namespace-wide
  default-deny with explicit allows (frontend, ingress controller, Prometheus,
  load generator). Enforcement requires a Calico-enabled cluster.
- **Tighter CORS.** Methods and headers are explicit lists instead of `*`.
- **Reproducible images.** MinIO and `mc` are pinned to specific release tags.

**Known dev-only items (state them honestly):** Postgres/MinIO use well-known
dev credentials so DataGrip and the MinIO console "just work" in class; the
ingress is HTTP-only (so `REFRESH_COOKIE_SECURE` stays `false`); `config.py`
keeps a weak `SECRET_KEY` default that the Kubernetes Secret overrides. Rotate
credentials and add TLS (e.g. cert-manager) before any shared deployment.

---

## 11. How autoscaling works (HPA)

- `metrics-server` (a minikube addon) collects CPU/memory from each pod.
- The HPA periodically computes: `desiredReplicas = ceil(currentReplicas × currentCPU / targetCPU)`.
- `targetCPU` is 70% **of the pod's CPU request** (100m), i.e. ~70m per pod.
  Under load each pod easily exceeds that, so it scales out, up to `maxReplicas: 6`.
- `behavior` tunes the speed: scale up fast (30s window), scale down slow (180s)
  to avoid flapping.
- The PDB (`minAvailable: 1`) guarantees the API never goes fully offline during
  voluntary disruptions (node drain, rolling update).

Inspect it: `kubectl describe hpa backend -n forum-wedkarskie`.

---

## 12. How monitoring works

- **Metrics:** the backend exposes Prometheus metrics at `/metrics`
  (`prometheus-fastapi-instrumentator`). The `ServiceMonitor` tells the
  Prometheus Operator to scrape `backend-service:8000/metrics` every 15s.
  Prometheus is configured (Helm values) to discover ServiceMonitors in all
  namespaces, so it finds the app's.
- **Logs:** Promtail (a DaemonSet) tails every pod's stdout/stderr and ships it
  to Loki. Grafana has Loki wired as a datasource, so logs and metrics share one
  UI. Query by `{namespace="forum-wedkarskie"}`.
- **Dashboard:** `grafana-dashboard-forum.yaml` is a ConfigMap labelled
  `grafana_dashboard: "1"`; Grafana's sidecar auto-imports it — no manual upload.
- **Alerts:** `prometheus-rules.yaml` defines example alerts (backend down, high
  5xx rate, high p95 latency, HPA at max) visible in Prometheus → Alerts and
  Grafana → Alerting.

Key metric names used: `http_requests_total{handler,status,method}` (counter),
`http_request_duration_highr_seconds_bucket` (histogram), plus
`container_cpu_usage_seconds_total` / `container_memory_working_set_bytes` and
`kube_horizontalpodautoscaler_status_*` from kube-state-metrics.

---

## 13. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Pods stuck `ImagePullBackOff` | Images not built into the minikube daemon. Run `minikube -p minikube docker-env --shell powershell \| Invoke-Expression` then rebuild, or use `deploy.ps1 -Build`. |
| `kubectl top` says "metrics not available" | `minikube addons enable metrics-server`, wait ~30s. |
| HPA shows `<unknown>/70%` | Same as above — metrics-server not ready yet. |
| `forum.local` doesn't resolve | Missing hosts entry. Add `<minikube ip>  forum.local` to `C:\Windows\System32\drivers\etc\hosts` (as Administrator). |
| Ingress 404 / connection refused | `minikube addons enable ingress`; wait for the `ingress-nginx-controller` pod to be Ready. |
| File upload URLs broken in browser | `MINIO_PUBLIC_ENDPOINT` not set to the real IP. `deploy.ps1` renders it; if manual, substitute `<minikube-ip>`. |
| Backend `CrashLoopBackOff` after enabling read-only FS | A path needs to be writable. The manifest mounts `/tmp` (emptyDir) and `/app/uploads` (PVC); if a new write path appears, add an emptyDir or set `readOnlyRootFilesystem: false`. |
| Migration Job fails | `kubectl logs job/backend-migrate -n forum-wedkarskie`. Usually Postgres wasn't ready or a bad migration; `deploy.ps1 -Clean` to reset the DB volume. |
| Grafana has no "Forum Overview" | The dashboard ConfigMap is in `monitoring`; ensure `install-monitoring.ps1` ran and the Grafana sidecar is enabled (it is, in the values). |
| NetworkPolicies "don't block anything" | Expected on the default CNI. Use `minikube start --cni=calico` to enforce. |

Reset everything:
```powershell
kubectl delete namespace forum-wedkarskie monitoring
# or nuke the cluster entirely:
minikube delete
```

---

## 14. Out of scope (intentionally not done)

Consistent with the project's stabilization decision: RabbitMQ, WebSockets,
TLS/cert-manager on the ingress, and a CI/CD pipeline (GitHub Actions running
`kubectl apply --dry-run` + tests) are **not** included. The monitoring,
scaling, and security pieces needed for the Kubernetes course are complete and
demonstrable with the steps above.

---

*End of runbook. The only repo changes from this documentation step is the
creation of this file.*
