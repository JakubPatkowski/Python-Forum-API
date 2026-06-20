# Deployment

The application runs on **Kubernetes (minikube)** in the `forum-wedkarskie`
namespace. Images are built locally into minikube's Docker daemon, so all
manifests use `imagePullPolicy: Never`.

## Containers

Both services ship as Docker images:

- **backend** — multi-stage build with `uv`, runs as a non-root user (uid 1000).
- **frontend** — built with Vite, served by nginx (`client_max_body_size 30m` so large uploads pass through).

## Kubernetes manifests (`k8s/`)

| Area | Resources |
|------|-----------|
| **namespace** | `forum-wedkarskie` |
| **postgres** | Deployment, PVC, Secret |
| **backend** | Deployment (securityContext non-root), ConfigMap, **Secret** (`SECRET_KEY`), HPA (1–3, 70% CPU), PDB, migration Job, orphan-cleanup CronJob, uploads PVC, Service |
| **frontend** | Deployment, ConfigMap, HPA, Service |
| **minio** | Deployment, PVC, Secret, bucket-creation Job, Service |
| **ingress** | App ingress (`forum.local`) and monitoring ingress (`grafana.local`) |
| **network-policies** | `postgres-allow-backend` plus a `full-lockdown` variant (default-deny + explicit allows) |
| **monitoring** | kube-prometheus-stack + Loki values, ServiceMonitor, Prometheus rules, two Grafana dashboards |

Database migrations run as a **Job** before the backend rolls out — never as
`create_all` at runtime.

## Deploy order

1. Start minikube with enough resources for the monitoring stack.
2. Build the backend and frontend images directly into minikube's Docker daemon.
3. Create the namespace and secrets (copy each `*.example.yaml` to `*.yaml` and fill in values).
4. Apply Postgres, then run the migration Job.
5. Apply everything else (backend, frontend, MinIO, ingress, HPA, PDB, CronJob).
6. Map `forum.local` / `grafana.local` to the minikube IP and open the app.

The `scripts/start-demo.sh` wrapper automates this flow (build, deploy, monitoring,
port-forwards) end to end.

## Operational scripts (`scripts/`)

The project is developed and run from Ubuntu WSL, so the operational tooling is
provided as bash scripts.

| Script | Purpose |
|--------|---------|
| `start-demo.sh` | Full build-and-deploy + monitoring + port-forwards (`--build`, `--stop`) |
| `run-load-test.sh` | Run a k6 load-test profile (`smoke`/`demo`/`stress`) and generate the HTML report |
| `seed-test-data.sh` | Seed demo content (users, categories, posts, comments) for screenshots/demo |
| `validate-app.sh` | Health snapshot: pods, restarts/OOM, HPA, CPU/RAM, health probes, log tails |
| `setup-check.sh` | Check (and with `--install`, install) WSL tooling: Docker, kubectl, minikube, helm, uv, pnpm |
| `e2e-smoke.sh` | End-to-end smoke test against a running deployment (also run in CI) |

To reset the database in Kubernetes, delete the Postgres PVC and restart the
deployment (migrations re-run via the Job):

```bash
kubectl delete pvc postgres-pvc -n forum-wedkarskie
kubectl rollout restart deploy/postgres -n forum-wedkarskie
```

## Local development (Docker Compose)

For day-to-day backend/frontend work, `docker compose up --build` runs Postgres,
MinIO, and the backend. After a schema change on an existing volume, reset with
`docker compose down -v` before bringing the stack back up.

See also: [Monitoring](./05-monitoring.md) · [Testing](./06-testing.md) ·
[Development](./07-development.md).
