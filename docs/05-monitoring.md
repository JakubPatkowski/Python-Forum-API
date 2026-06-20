# Monitoring & Observability

## Metrics

The backend exposes Prometheus metrics at `/metrics` via
`prometheus-fastapi-instrumentator`. In the cluster, the **kube-prometheus-stack**
Helm chart scrapes the backend through a `ServiceMonitor`, and **Prometheus rules**
define alerting/recording expressions.

## Dashboards

Two **Grafana** dashboards ship as ConfigMaps:

- `grafana-dashboard-forum` — application and infrastructure metrics (request rate, latency, CPU, HPA replica count).
- `grafana-dashboard-presentation` — a trimmed view for live demos.

Grafana is reachable at `grafana.local` through the monitoring ingress.

## Logs

Structured JSON logs are emitted to stdout with **structlog** and collected by
**Loki** in the cluster, queryable from Grafana.

## Resource tuning (16 GB RAM)

The monitoring stack is deliberately trimmed to fit a 16 GB development machine:
Grafana is capped at 512 Mi, Alertmanager is disabled, and the Grafana CPU limit
was raised (300m → 800m) to avoid throttling-induced crashes under load tests.

## What's in place vs planned

In place: `/metrics`, structlog, Prometheus + Grafana + Loki, ServiceMonitor,
Prometheus rules, HPA-visible scaling. Planned: request-id middleware and
distributed tracing.

See also: [Deployment](./04-deployment.md) · [Testing](./06-testing.md).
