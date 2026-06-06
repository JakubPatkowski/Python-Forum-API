# Backend + Kubernetes + Docker Audit Report (2026-06-04)

## Scope
- Backend code under `backend/app` and `backend/tests`
- Docker configuration in `docker-compose.yml`
- Kubernetes manifests under `k8s/`

## Method
- Manual review of code and manifests
- Focus on security risks, logic errors, architectural cleanliness, dead code, and operational readiness

## Findings (ordered by severity)

### Critical
- **JWT secret stored in a ConfigMap**: `SECRET_KEY` is committed in plain text, allowing token forgery if the repo leaks. Move to a Secret and reference it from the Deployment. [k8s/backend/configmap.yaml](k8s/backend/configmap.yaml#L7-L12)
- **Default JWT secret in runtime settings**: A weak default is baked into the settings; if env is missing, you risk running with a known secret. [backend/app/config.py](backend/app/config.py#L13-L19)

### High
- **Readiness probe does not exercise DB check**: K8s probes use `/health`, but the DB-backed readiness is on `/health/ready`. This makes readiness less reliable under DB outages. [k8s/backend/deployment.yaml](k8s/backend/deployment.yaml#L32-L41), [backend/app/main.py](backend/app/main.py#L167-L179)
- **MinIO console exposed via NodePort**: Port 9001 is exposed to the host network. This is fine for local dev but should be locked down (NetworkPolicy/Ingress restriction) for any shared environment. [k8s/minio/service.yaml](k8s/minio/service.yaml#L16-L23)
- **Wildcard CORS methods and headers**: Origins are explicit (good), but methods/headers are fully open. This widens the attack surface unnecessarily. [backend/app/main.py](backend/app/main.py#L76-L84)

### Medium
- **Weak dev credentials hardcoded**: Default PostgreSQL and MinIO credentials are embedded in `docker-compose.yml`. This is acceptable for local dev but should be documented as dev-only and rotated for any shared environment. [docker-compose.yml](docker-compose.yml#L5-L39)
- **MinIO image pinned to `latest`**: Non-deterministic deployments and surprise upgrades. Pin a specific tag in k8s and compose. [k8s/minio/deployment.yaml](k8s/minio/deployment.yaml#L19-L21), [docker-compose.yml](docker-compose.yml#L67-L73)
- **Missing resource requests/limits on Postgres and Frontend**: Both deployments lack resource constraints; this can starve the cluster under load. [k8s/postgres/deployment.yaml](k8s/postgres/deployment.yaml#L16-L26), [k8s/frontend/deployment.yaml](k8s/frontend/deployment.yaml#L16-L25)
- **Structured logging gap**: One maintenance script uses `print` instead of structured logging, which breaks log consistency. [backend/app/maintenance/cleanup_orphan_files.py](backend/app/maintenance/cleanup_orphan_files.py#L53-L56)
- **Raw SQL with f-string even when whitelisted**: Engagement endpoints build SQL with interpolated table name. It is whitelisted (so safe), but still an antipattern that invites future mistakes. [backend/app/modules/engagement/router.py](backend/app/modules/engagement/router.py#L56-L63)

### Low
- **ConfigMap contains dev defaults for DB**: The in-cluster `DATABASE_URL` uses `postgres:postgres`. This is fine for a student cluster, but note it is not production-safe. [k8s/backend/configmap.yaml](k8s/backend/configmap.yaml#L7-L9)

## Architecture and Code Cleanliness
- **Strengths**: Clear Clean Architecture separation, modular monolith structure, and strong domain boundaries. The routing layout in [backend/app/main.py](backend/app/main.py#L63-L146) is tidy and explicit.
- **Debt to watch**: The engagement module is intentionally thin and uses raw SQL; this is acceptable for the current phase but will be harder to extend for richer domain logic later. [backend/app/modules/engagement/router.py](backend/app/modules/engagement/router.py#L1-L220)
- **Operational readiness**: A real DB-backed readiness check exists and `/metrics` is exposed; this is good for future monitoring, but the k8s manifests do not yet wire ServiceMonitor/HPA/NetworkPolicy.

## Security Notes
- The combination of committed secrets and permissive CORS methods/headers is the most urgent risk to address.
- MinIO admin console exposure is acceptable for local-only setups but not for any shared or grading environment where others can reach NodePorts.

## Observability Readiness
- `/metrics` is available in the app and logging is structured via `structlog`.
- To add Prometheus/Grafana later, the app is ready; the missing piece is Kubernetes wiring (ServiceMonitor, scrape config, and alerts).

## Recommended Fix Order (fastest value first)
1. Move `SECRET_KEY` from ConfigMap to Secret and require it in runtime config.
2. Update readiness probe to `/health/ready` and keep `/health` only for legacy.
3. Tighten CORS methods/headers to just what the API uses.
4. Pin MinIO versions (compose + k8s).
5. Add resource requests/limits for Postgres and Frontend.
6. Replace `print` with `logger.info` in maintenance.
7. Consider replacing f-string SQL in engagement with safer patterns.

## Open Items for Next Iteration
- Add HPA and NetworkPolicy manifests for backend/postgres/minio.
- Add Prometheus/Grafana deployment and ServiceMonitor for `/metrics`.
- Decide on the final posture for MinIO console exposure in k8s.

---
If you want, I can turn these findings into a concrete fix plan and start applying the highest-priority changes in order.