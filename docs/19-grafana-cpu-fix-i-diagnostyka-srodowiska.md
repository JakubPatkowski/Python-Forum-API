# 19 — Grafana CPU/memory fix, diagnostyka środowiska, upload plików

Date: 2026-06-05. Sesja naprawcza: metryki Grafany (CPU/memory by pod), skrypt
diagnostyczny środowiska, identyfikacja problemu z uploadem plików w k8s.

## Co zostało naprawione

### 1. Grafana — Backend CPU/memory by pod (No data → działa)

**Symptom:** Panele "Backend CPU usage by pod" i "Backend memory (working set) by pod"
w Forum Overview pokazywały "No data" mimo że cAdvisor był aktywny.

**Przyczyna:** Na minikube z driverem `docker` metryki `container_cpu_usage_seconds_total`
mają **pusty label `image`** oraz brak labela `container`. Poprzedni fix używał filtra
`image!=""` — który na tym setupie zawsze daje 0 serii. Serie są jednak dostępne i
mają label `cpu="total"` (jeden per pod).

**Fix** (`k8s/monitoring/grafana-dashboard-forum.yaml`):
```promql
# przed (No data):
sum(rate(container_cpu_usage_seconds_total{namespace="forum-wedkarskie",pod=~"backend-.*",image!=""}[1m])) by (pod)

# po (działa):
sum(rate(container_cpu_usage_seconds_total{namespace="forum-wedkarskie",pod=~"backend-.*",cpu="total"}[1m])) by (pod)
```

Memory — usunięto filtr `image!=""`, zostało samo `pod=~"backend-.*"`:
```promql
# po:
sum(container_memory_working_set_bytes{namespace="forum-wedkarskie",pod=~"backend-.*"}) by (pod)
```

**Zaaplikować:**
```powershell
kubectl apply -f k8s/monitoring/grafana-dashboard-forum.yaml
# Grafana auto-importuje ConfigMap w ~30s
```

### 2. cAdvisor TLS fix (values-kube-prometheus-stack.yaml)

Dodano jawne opcje TLS dla scrape'owania cAdvisora przez kubelet na minikube:
```yaml
kubelet:
  enabled: true
  serviceMonitor:
    cAdvisor: true
    https: true
    insecureSkipVerify: true
    bearerTokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token
```

Bez tych ustawień Prometheus może dostawać błędy TLS/401 przy scrape `/metrics/cadvisor`.
**Wymagany `helm upgrade` po każdej zmianie values.**

### 3. Stare obrazy w minikube (pułapka z docker-env)

**Symptom:** `diagnose-env.ps1` pokazał obrazy z 23 maja mimo że deploy był robiony dziś.

**Przyczyna:** `deploy.ps1 -Build` najpierw robi `docker build`, a `minikube docker-env`
jest wywoływany w kroku 2 — ale gdy PowerShell nie ma aktywnego `Invoke-Expression`
z `minikube docker-env`, `docker build` trafia do Docker Desktop zamiast do minikube.
Obrazy w minikube pozostają stare (z poprzedniego `-Build`).

**Jak sprawdzić:** W Prometheus Explore zapytaj o datę uruchomienia poda:
```promql
kube_pod_start_time{namespace="forum-wedkarskie",pod=~"backend-.*"}
```

**Właściwy flow buildu:**
```powershell
# Musi być w jednej sesji PowerShell:
minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t forum-wedkarskie-backend:latest backend/
# ... dopiero potem kubectl apply
```
`deploy.ps1` robi to poprawnie — ale tylko gdy jest uruchamiany jako całość, nie
przez kopiowanie pojedynczych kroków.

### 4. Skrypt diagnostyczny środowiska

Nowy skrypt: `scripts/diagnose-env.ps1`

Sprawdza 7 sekcji:
1. Windows — wirtualizacja CPU, Hyper-V, WSL2, RAM
2. Docker Desktop — daemon, kontekst, pamięć, CPU, obrazy aplikacji
3. minikube — status, driver, pamięć (czyta z profilu, nie z config), addony
4. Kubernetes — pody, PVC, sekrety
5. Sieć — minikube tunnel, hosts, MinIO NodePort, MINIO_PUBLIC_ENDPOINT
6. Prometheus/cAdvisor — port-forward, targety, serie container_cpu/memory, cluster label
7. MinIO — pod, bucket, in-cluster connectivity (przez python, nie curl)

**Pułapki w skrypcie (naprawione):**
- `minikube config get memory` zwraca pustą wartość gdy pamięć ustawiana przez `--memory` — czytaj z `minikube profile list -o json`
- `minikube addons list -o json` format JSON nie jest prostą tablicą — fallback przez `kubectl get deployment`
- `curl` nie istnieje w slim Python image — użyj `python -c "urllib.request..."`
- Pod w stanie `Succeeded` (CronJob) to normalny stan, nie FAIL
- cAdvisor na minikube może nie mieć osobnego targetu Prometheus — weryfikuj przez liczenie serii `container_cpu`

## Problem z uploadem plików (nierozwiązany)

**Symptom:** Upload plików nie działa w UI.

**Co wiadomo:**
- Backend → MinIO (in-cluster): HTTP 200 ✅ — sieć działa
- MinIO NodePort `192.168.49.2:30900` nieosiągalny z Windows ⚠️

**Prawdopodobna przyczyna:** Presigned URL generowany przez backend zawiera
`MINIO_PUBLIC_ENDPOINT = 192.168.49.2:30900`. Przeglądarka na Windows nie może
dotrzeć do IP minikube node bezpośrednio — `minikube tunnel` obsługuje tylko
LoadBalancer/Ingress, nie NodePort.

**Rozwiązanie (do wdrożenia):** Zmień `MINIO_PUBLIC_ENDPOINT` na `localhost:30900`
i dodaj port-forward dla MinIO do `portforward.ps1`. Lub użyj ingress dla MinIO S3.

**Weryfikacja problemu:**
```powershell
# Zaloguj, zrób upload, sprawdź presigned URL w odpowiedzi:
# FileResponse.download_url powinien zawierać host osiągalny z przeglądarki
```

## Pozostałe WARNy (akceptowalne)

| WARN | Wyjaśnienie |
|------|-------------|
| Hyper-V state: (pusty) | WMI nie zwraca stanu — nie wpływa na działanie (driver=docker) |
| RAM 15.4 GB | Poniżej rekomendowanych 16 GB — działa ale ciasno przy 6 replikach + monitoring |
| MinIO NodePort nieosiągalny | Patrz sekcja "upload" powyżej |
| Backend /health via forum.local | `minikube tunnel` musi działać jako Administrator |
| cluster label missing | `helm upgrade` zaaplikowany ale Prometheus nie był zrestartowany — nowe samples dopiero będą miały label |

## Komendy do użycia po zmianach

```powershell
# Po zmianie grafana-dashboard-forum.yaml:
kubectl apply -f k8s/monitoring/grafana-dashboard-forum.yaml

# Po zmianie values-kube-prometheus-stack.yaml:
helm upgrade monitoring prometheus-community/kube-prometheus-stack `
  --namespace monitoring `
  -f k8s/monitoring/values-kube-prometheus-stack.yaml

# Diagnostyka środowiska:
.\scripts\diagnose-env.ps1   # wymaga aktywnego .\scripts\portforward.ps1
```
