# 18 — Grafana "No data" panels: diagnosis & fix

Date: 2026-06-05. Scope: why several Grafana panels showed **No data** and what was
changed to fix them. Touches `k8s/monitoring/values-kube-prometheus-stack.yaml` and
`k8s/monitoring/grafana-dashboard-forum.yaml`.

## Symptom

In Grafana, panels rendered "No data" in three places:

- **Forum Overview** (our custom dashboard): `Backend CPU usage by pod`, `Backend memory (working set) by pod`.
- **Kubernetes / Compute Resources / Namespace (Pods)** (stock dashboard): `CPU Quota`, `Memory Quota`, `CPU/Memory Utilisation (from requests/limits)`, `Memory Requests by Cluster`.
- **Networking** sections (stock): `Receive/Transmit Bandwidth`, `Rate of Received/Transmitted Packets`, `... Packets Dropped`, `Current/Average Rate of Bits Received/Transmitted`.

Importantly, the stack itself was healthy: all Prometheus targets were `up`
(kubelet, kube-state-metrics, node-exporter, cadvisor), and ad-hoc queries returned
data. So this was **not** a dead exporter — it was three independent causes.

## Diagnosis (how it was confirmed)

Queried Prometheus directly via port-forward (`svc/prometheus-operated`):

| Query | Result | Meaning |
|-------|--------|---------|
| `container_cpu_usage_seconds_total{namespace="forum-wedkarskie"}` | 10 series | cAdvisor CPU **present** |
| `container_cpu_usage_seconds_total{...,container="backend"}` | 0 series | `container` label is **empty** on minikube |
| `container_network_receive_bytes_total` (all namespaces) | 0 series | no per-pod network metrics at all |
| raw kubelet `/metrics/cadvisor` for `container_network_*` | 2 lines, `pod=""`, `namespace=""`, `id="/"` | only node-level network, never per-pod |
| `kube_pod_container_resource_requests{namespace="forum-wedkarskie"}` | 26 series | kube-state-metrics **present** |
| labels on `container_cpu_usage_seconds_total` | `__name__, cpu, endpoint, id, instance, job, metrics_path, namespace, node, pod, service` | **no `cluster` label** |

## Root causes & fixes

### Cause A — empty `container` label broke our two custom panels

On minikube, cAdvisor does **not** populate the per-container `container` label, so a
filter `container="backend"` matches nothing (0 series), even though querying the same
pods without that filter returns 6 series. The container *is* named `backend` in the
Pod spec — the label just isn't exported.

**Fix** (`grafana-dashboard-forum.yaml`): drop `container="backend"` and instead select
by pod name plus `image!=""` to exclude the pod-sandbox/`POD` pseudo-container series:

```promql
# before (No data):
sum(rate(container_cpu_usage_seconds_total{namespace="forum-wedkarskie",pod=~"backend-.*",container="backend"}[1m])) by (pod)
# after (works):
sum(rate(container_cpu_usage_seconds_total{namespace="forum-wedkarskie",pod=~"backend-.*",image!=""}[1m])) by (pod)
```

Same change applied to the memory panel (`container_memory_working_set_bytes`).
English `description` fields were added to every panel in the dashboard.

### Cause B — missing `cluster` label broke the stock dashboards

The stock kube-prometheus-stack dashboards filter every query by `cluster="$cluster"`.
Our metrics carried no `cluster` label, so the `$cluster` template variable was empty
and the queries returned nothing — despite kube-state-metrics being healthy.

**Fix** (`values-kube-prometheus-stack.yaml`): stamp all samples with an external label.

```yaml
prometheus:
  prometheusSpec:
    externalLabels:
      cluster: forum-wedkarskie
```

After a `helm upgrade` + Prometheus restart, the `$cluster` dropdown populates and the
CPU/Memory/Quota/Utilisation panels render data.

### Cause C — no per-pod network metrics on minikube (known limitation, not fixed)

cAdvisor on this minikube only emits **node-level** network counters (`id="/"`, empty
`pod`/`namespace`); there are zero per-pod `container_network_*` series at the source.
Prometheus correctly drops the unattributed node-level series via the default kubelet
`metricRelabelings`, leaving nothing for the network panels.

This is a **minikube/CNI limitation**, not a configuration bug. The container runtime
does not expose per-pod network statistics that cAdvisor can break down. It cannot be
fixed with Helm values or relabeling — only by switching the minikube driver/CNI and
restarting the cluster, which is out of scope for this project.

**Consequence:** the Networking panels in the stock dashboards (Bandwidth, Packets,
Bits Received/Transmitted) stay empty. We accept this. Per-pod CPU and memory — the
metrics that actually matter for the HPA/load-test story — work fine. The stock
dashboards cannot be disabled individually (the chart has no per-dashboard toggle;
only the global `grafana.defaultDashboardsEnabled`), so they are left enabled and this
caveat is documented here instead.

## How to apply

```powershell
# from repo root
helm upgrade monitoring prometheus-community/kube-prometheus-stack `
  --namespace monitoring `
  -f k8s/monitoring/values-kube-prometheus-stack.yaml

# the custom dashboard is a ConfigMap, re-apply it (sidecar auto-imports):
kubectl apply -f k8s/monitoring/grafana-dashboard-forum.yaml
```

Then in Grafana:

- Wait ~1-2 min for Prometheus to restart and re-scrape (external labels apply to new samples).
- In a stock dashboard, set the `cluster` variable to `forum-wedkarskie` and `namespace` to `forum-wedkarskie` (the screenshot showed `namespace=default`, which is also empty for us).
- Forum Overview "Backend ... by pod" panels show data immediately after the ConfigMap re-apply.

## Verification

Re-run the diagnostic query for the fixed panels after upgrade:

```powershell
$base = "http://localhost:9099/api/v1"
function Q($q){ (Invoke-RestMethod "$base/query?query=$([uri]::EscapeDataString($q))").data.result.Count }
Q 'sum(rate(container_cpu_usage_seconds_total{namespace="forum-wedkarskie",pod=~"backend-.*",image!=""}[1m])) by (pod)'   # expect > 0
Q 'kube_pod_container_resource_requests{namespace="forum-wedkarskie",cluster="forum-wedkarskie"}'                          # expect > 0
```

If the second returns 0 but the unfiltered version returns >0, Prometheus hasn't been
restarted yet (external labels apply only to samples scraped after restart) — give it
another minute.
