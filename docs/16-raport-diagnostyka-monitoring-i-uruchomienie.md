# 16 — Raport diagnostyczny: monitoring, sieć i uruchamianie

> **Cel.** Odpowiedź na realne problemy ze stanu na 2026-06-05: K8s wstaje, frontend/backend
> działają, Grafana i Prometheus chodzą, ale: część paneli pokazuje **No data**, **Loki nie
> działa**, aplikacja działa **tylko z port-forwardem**, a skrypty bywają kruche (znaki spoza
> UTF-8 / em-dashy). Ten dokument mówi **co jest zrobione, co wymaga dopracowania i jak to
> naprawić** — bez powtarzania znanych błędów z docs/14 i docs/15.
>
> Data: 2026-06-05 · kod ~0.3.0 · **ten plik niczego nie zmienia w kodzie** (sama diagnoza + instrukcje).

---

## 0. TL;DR

Stack **działa funkcjonalnie**. Problemy są operacyjne i kosmetyczne, nie architektoniczne:

| Objaw | Przyczyna (root cause) | Trudność naprawy |
|-------|------------------------|------------------|
| Panele „CPU/memory by pod", „Compute Resources" = **No data** | Prometheus nie scrapuje cAdvisor/kubelet na minikube (metryki `container_*` nie istnieją) | Średnia |
| Panel „Error rate (5xx)" = **No data** | To **nie błąd** — po prostu nie było żadnego ruchu 5xx, więc dzielenie zwraca pustą serię | Trywialna (kosmetyka) |
| **Loki nie działa** | Nazwa serwisu Loki ≠ URL w datasource Grafany; chart `loki-stack` jest deprecated | Średnia |
| Aplikacja **tylko przez port-forward** | Brak `minikube tunnel` (Windows nie routuje 192.168.49.0/24); ingress kieruje tylko `/` na frontend | Łatwa |
| Skrypty czasem nie startują | Pliki `.ps1` zapisane jako **UTF-8 bez BOM** z em-dashami (`—`) → PowerShell 5.1 czyta śmieci | Łatwa |

**Jednozdaniowo:** projekt jest gotowy na demo; trzeba poprawić 5 rzeczy operacyjnych, z czego dwie (port-forward i skrypty) są krytyczne dla „żeby się odpalało".

---

## 1. Co jest faktycznie zrobione (działa)

Potwierdzone z manifestów i ze zrzutów Grafany:

- **Aplikacja w K8s**: backend (HPA 2-6, widać **6 replik** w panelu), frontend, postgres, MinIO — wszystkie wstają, migracje Alembic jako Job.
- **Prometheus scrapuje backend**: panele „Request rate" (22.3 req/s), „p95 latency" (9.839 ms), „Request rate by handler", „Latency p50/p95/p99" **mają dane** → `ServiceMonitor` działa, `/metrics` jest scrapowany, `http_requests_total` i histogram `highr` istnieją.
- **HPA + kube-state-metrics**: panel „Backend replicas (HPA)" = 6, „current vs desired" rysuje linie → `kube_horizontalpodautoscaler_*` i `kube_deployment_*` działają.
- **Dashboard auto-import**: „Forum Overview" wczytał się sam przez sidecar (ConfigMap z labelem `grafana_dashboard: "1"`).
- **Hardening**: securityContext, probes live/ready, resources, PDB, NetworkPolicy, secrety poza ConfigMap — wszystko w repo (szczegóły w docs/12 §2).

To jest solidna podstawa. Poniżej tylko to, co wymaga ręki.

---

## 2. Problem: panele „No data" (CPU/RAM podów, Compute Resources)

### 2.1. Diagnoza

Panele, które **mają dane**, pytają o metryki aplikacji (`http_requests_total`) i kube-state-metrics
(`kube_*`). Panele, które pokazują **No data**, pytają o metryki **kontenerów z cAdvisora**:

```
container_cpu_usage_seconds_total{...}
container_memory_working_set_bytes{...}
```

Te metryki pochodzą z **kubeletu / cAdvisora**, nie z naszego backendu. Na minikube kube-prometheus-stack
**często nie scrapuje kubeletu poprawnie** (TLS do `:10250`, self-signed cert, albo target po prostu Down).
Stąd „Compute Resources / Multi-Cluster" → CPU Usage / Memory Usage = No data, a nasze panele
„Backend CPU/memory by pod" też.

**To nie jest błąd w dashboardzie — to brak źródła metryk.** Zapytania są poprawne.

### 2.2. Jak potwierdzić (1 minuta)

W Prometheus (`localhost:9090`) → **Status → Targets**. Szukaj targetów `kubelet` / `cadvisor`:
- jeśli **Down / Unknown** → to jest przyczyna.

Albo w **Graph** wpisz `container_cpu_usage_seconds_total` — jeśli „Empty query result", metryki nie ma.

### 2.3. Naprawa

**Opcja A (zalecana, najprostsza):** włącz dedykowany kubelet service monitor i pozwól na niezaufany cert.
Dodaj do `k8s/monitoring/values-kube-prometheus-stack.yaml`:

```yaml
kubelet:
  enabled: true
  serviceMonitor:
    cAdvisor: true

# Pod minikube kubelet ma self-signed cert — pozwól operatorowi go nie weryfikować.
# (Sekcja kubelet w kube-prometheus-stack scrapuje cadvisor przez /metrics/cadvisor.)
prometheus:
  prometheusSpec:
    # ... istniejące pola ...
    kubeletService:
      enabled: true
```

Potem:

```powershell
helm upgrade monitoring prometheus-community/kube-prometheus-stack `
  --namespace monitoring -f k8s/monitoring/values-kube-prometheus-stack.yaml
```

**Opcja B (szybki test bez reinstalacji):** sprawdź czy metrics-server żyje — to inne źródło niż cAdvisor,
ale potwierdza, że kubelet w ogóle oddaje metryki:

```powershell
kubectl top pods -n forum-wedkarskie
```

Jeśli `kubectl top` działa, a panele nie — problem jest po stronie scrape'a cAdvisora przez Prometheusa
(Opcja A). Jeśli `kubectl top` też nie działa → `minikube addons enable metrics-server` i poczekaj 60 s.

> **Uwaga praktyczna na demo:** jeśli nie chcesz dłubać w kubelet TLS, panele CPU/RAM podów możesz
> **na żywo pokazać przez `kubectl top pods` i `minikube dashboard`** — komisja zobaczy zużycie zasobów,
> a w Grafanie skupisz się na panelach RPS/latency/HPA, które działają. To w pełni wystarcza na zaliczenie.

### 2.4. Panel „Error rate (5xx) = No data" — to NIE problem

Query: `100 * sum(rate(5xx)) / clamp_min(sum(rate(all)), 1)`. Gdy w oknie czasu nie było **żadnego**
żądania 5xx, licznik `http_requests_total{status=~"5.."}` nie ma serii i całość zwraca pustą wartość →
Grafana renderuje „No data" zamiast `0`. **To znaczy, że aplikacja nie zwraca błędów** — czyli dobrze.

Jeśli chcesz, żeby pokazywało `0` zamiast „No data" (ładniej na demo), zmień target w dashboardzie na:

```promql
100 * (sum(rate(http_requests_total{namespace="forum-wedkarskie",status=~"5.."}[5m])) or vector(0))
      / clamp_min(sum(rate(http_requests_total{namespace="forum-wedkarskie"}[5m])), 1)
```

`or vector(0)` wstrzykuje zero, gdy nie ma żadnej serii 5xx.

---

## 3. Problem: Loki nie działa

### 3.1. Diagnoza

Dwie nakładające się przyczyny:

1. **Mismatch nazwy serwisu.** Datasource w `values-kube-prometheus-stack.yaml`:
   ```
   url: http://loki.monitoring.svc.cluster.local:3100
   ```
   Chart `grafana/loki-stack` instalowany z release name `loki` tworzy serwis o nazwie zależnej od
   `fullnameOverride`. Jeśli serwis nazywa się np. `loki` — URL jest OK; jeśli `loki-stack` albo
   `loki-headless` — Grafana dostaje connection refused i panel logów oraz Explore→Loki są puste.

2. **Chart jest deprecated** — w logu deploya widać `level=WARN msg="this chart is deprecated"`.
   Działa, ale bywa kapryśny; nowsze setupy używają `grafana/loki` + `grafana/promtail` osobno.

### 3.2. Jak potwierdzić (1 minuta)

```powershell
kubectl get svc -n monitoring | Select-String -Pattern "loki"
kubectl get pods -n monitoring | Select-String -Pattern "loki|promtail"
```

- Zapamiętaj **dokładną nazwę serwisu** Loki (kolumna NAME).
- `promtail-*` musi być **Running** na każdym node (DaemonSet). Jeśli promtail nie wstał, nie ma logów do zbierania.

Test z wnętrza Grafany — w Grafana → **Connections → Data sources → Loki → Save & test**:
- „Data source connected" = OK,
- błąd = zły URL (patrz niżej).

### 3.3. Naprawa

**Krok 1 — dopasuj URL do realnej nazwy serwisu.** Jeśli `kubectl get svc` pokazał np. `loki`, URL jest dobry.
Jeśli pokazał inną nazwę, popraw w `values-kube-prometheus-stack.yaml`:

```yaml
additionalDataSources:
  - name: Loki
    type: loki
    access: proxy
    url: http://<DOKŁADNA-NAZWA-SVC>.monitoring.svc.cluster.local:3100
    isDefault: false
```

i przeładuj Grafanę:

```powershell
helm upgrade monitoring prometheus-community/kube-prometheus-stack `
  --namespace monitoring -f k8s/monitoring/values-kube-prometheus-stack.yaml
kubectl rollout restart deployment monitoring-grafana -n monitoring
```

**Krok 2 — przypnij nazwę serwisu, żeby nie zgadywać.** Dodaj do `values-loki-stack.yaml`:

```yaml
loki:
  enabled: true
  fullnameOverride: loki      # gwarantuje serwis o nazwie dokładnie "loki"
  isDefault: false
  persistence:
    enabled: false
```

i reinstaluj:

```powershell
helm upgrade loki grafana/loki-stack `
  --namespace monitoring -f k8s/monitoring/values-loki-stack.yaml
```

Po tym URL `http://loki.monitoring.svc.cluster.local:3100` jest pewny.

**Krok 3 — sprawdź czy promtail w ogóle zbiera.** Promtail to DaemonSet montujący `/var/log/pods`.
Na minikube z Docker driver bywa, że ścieżki logów się nie zgadzają. Jeśli `promtail` jest Running,
ale Explore→Loki pusty, sprawdź:

```powershell
kubectl logs -l app.kubernetes.io/name=promtail -n monitoring --tail=50
```

Szukaj `level=error` o `open /var/log/pods/...: no such file`. Jeśli tak — to znany problem promtail+minikube;
najprostszy fix to przejść na `grafana/promtail` chart osobno (ma lepsze domyślne `scrapeConfigs` pod
containerd/docker). Ale na zaliczenie **wystarczy, że logi backendu widać w `kubectl logs`** — Loki to bonus.

> **Priorytet:** Loki jest „nice to have". Jeśli zżera czas, pokaż logi przez `kubectl logs deployment/backend -n forum-wedkarskie -f` i odhacz observability metrykami (Prometheus) — to działa.

---

## 4. Problem: aplikacja działa tylko z port-forwardem

### 4.1. Diagnoza

To jest **oczekiwane zachowanie minikube na Windows**, nie usterka. Z docs/15 wiadomo już:
Windows nie ma trasy do sieci `192.168.49.0/24`, więc `http://forum.local` i NodePort `:30080`
nie są osiągalne **bez** jednego z mechanizmów mostkujących. Port-forward działa, bo tuneluje
przez API server po localhost — dlatego „tylko to działa".

Dodatkowo: ingress `forum-app` ma regułę tylko dla `path: /` → `frontend-service`. To jest OK
(nginx frontendu proxuje `/api`, `/docs`), ale wymaga działającego ingressu + routingu do `192.168.49.2`.

### 4.2. Naprawa — wybierz JEDEN sposób dostępu

**Sposób A — `minikube tunnel` (do ingressu `forum.local`):**

```powershell
# Terminal 1 (zostaw otwarty!):
minikube tunnel
# Terminal 2:
# hosts (jako Administrator): <minikube ip>  forum.local
curl http://forum.local/health/ready
```

Po tunelu Windows dostaje trasę do LoadBalancer/ingress. **To jest właściwy sposób na demo ingressu.**

**Sposób B — `minikube service` (omija routing, otwiera URL z portem):**

```powershell
minikube service frontend-service -n forum-wedkarskie --url
# zwraca http://127.0.0.1:<losowy-port> i sam tuneluje
```

**Sposób C — port-forward (to, co już masz):** najpewniejsze, dobre na szybki development:

```powershell
.\scripts\portforward.ps1
```

> **Czego NIE robić (z docs/15):** nie odpalać `minikube delete` w trakcie aktywnego `minikube tunnel`
> (tunnel lock → split-brain). Jak coś się rozjedzie: `.\scripts\reset-minikube.ps1 -NoPrompt`.

### 4.3. Rekomendacja

Na obronę: **`minikube tunnel` + `forum.local`** wygląda najprofesjonalniej (czysty URL, widać ingress).
Na codzienny development: **port-forward** (mniej ruchomych części). Oba są poprawne — to nie jest błąd
do „naprawienia", tylko świadomy wybór trybu dostępu, który warto **opisać w README**.

---

## 5. Problem: skrypty kruche przez kodowanie (em-dashy / UTF-8 bez BOM)

### 5.1. Diagnoza — potwierdzona w plikach

Przeskanowałem wszystkie `.ps1`. Znaki **spoza ASCII** (głównie em-dash `—` U+2014 oraz polskie
litery w komentarzach) występują w UTF-8 **bez BOM**. Windows PowerShell 5.1 domyślnie czyta pliki
jako ANSI/Windows-1250, więc `—` i `ę` zamieniają się w krzaki — a gdy taki znak trafi do
kodu/parametru (nie tylko komentarza), skrypt potrafi się wyłożyć.

Konkretne miejsca:

| Plik | Linie z em-dash / non-ASCII |
|------|------------------------------|
| `deploy.ps1` | nagłówek (l.2) |
| `install-monitoring.ps1` | nagłówek (l.2) |
| `portforward.ps1` | nagłówek (l.2) |
| `run-load-test.ps1` | nagłówek (l.2) |
| `scaling-demo.ps1` | l.2, **l.20, l.31, l.40 — em-dash wewnątrz `Write-Host`** ← najgroźniejsze |

`generate-secrets.ps1`, `reset-db.ps1`, `reset-minikube.ps1` są czyste (ASCII).

To dokładnie pułapka opisana w docs/14 i w pamięci („em-dashy nie, UTF-8 bez BOM"). Najwyraźniej
część plików powstała/edytowała się bez przestrzegania tej zasady.

### 5.2. Naprawa — dwa ruchy

**Ruch 1 — usuń em-dashy.** Zamień każdy `—` na zwykły `-` albo `:`. Em-dash w skrypcie nie wnosi nic
poza ryzykiem. (Dotyczy zwłaszcza `scaling-demo.ps1` l.20/31/40, gdzie `—` jest w wyświetlanym tekście.)

**Ruch 2 — zapisz pliki jako UTF-8 **z BOM** (albo czyste ASCII).** W VS Code: prawy dolny róg →
„UTF-8" → **„Save with Encoding" → „UTF-8 with BOM"**. PowerShell 5.1 z BOM-em czyta poprawnie.

Masowo z PowerShella (uruchom raz, z katalogu repo):

```powershell
Get-ChildItem scripts\*.ps1 | ForEach-Object {
    $txt = Get-Content $_.FullName -Raw -Encoding UTF8
    $txt = $txt -replace [char]0x2014, '-' -replace [char]0x2013, '-'   # em/en-dash -> hyphen
    # zapis z BOM (domyślne UTF8 w PS 5.1 ma BOM):
    [System.IO.File]::WriteAllText($_.FullName, $txt, (New-Object System.Text.UTF8Encoding $true))
}
```

> **Zasada na przyszłość (z docs/14):** w skryptach `.ps1` — żadnych em-dashy ani „smart quotes";
> komentarze po polsku OK, ale plik **musi** być UTF-8 z BOM; edytuj w VS Code, nie w narzędziach,
> które zapisują UTF-8 bez BOM.

### 5.3. Dodatkowo: `deploy.ps1` nadal niekompletny (z docs/12 §0)

Z logu deploya widać, że `deploy.ps1 -Monitoring` **już robi** sporo (minikube, addony, secrety,
postgres, minio, migracje, workloady, monitoring) — czyli został rozbudowany względem stanu z docs/12.
To dobrze. Warto jeszcze dopisać na końcu **podpowiedź o `minikube tunnel`** (bo bez niego `forum.local`
z logu nie zadziała), żeby nie mylić użytkownika instrukcją, która wymaga tunelu.

---

## 6. Czy jest problem z komunikacją w Kubernetesie?

Krótko: **nie ma dowodów na realny problem komunikacji wewnątrz klastra.** Argumenty:

- Backend scrapuje się przez Prometheusa (panele RPS/latency mają dane) → `backend-service` ma endpointy,
  DNS klastra działa, ServiceMonitor trafia do podów.
- HPA pokazuje 6 replik → metrics-server + kube-state-metrics gadają z API serverem.
- Migracje przeszły (Job `backend-migrate` complete) → backend łączy się z postgresem (NetworkPolicy
  `postgres-allow-backend` przepuszcza pody `app: backend`).

Objawy, które Cię zaniepokoiły, mają inne źródła: **No data** = brak scrape'a cAdvisora (nie sieć),
**Loki** = nazwa serwisu/datasource (nie sieć), **tylko port-forward** = routing Windows↔minikube (nie sieć K8s).

Jedyne, co mogłoby udawać „problem komunikacji": jeśli włączysz `network-policies/full-lockdown/`
**bez CNI Calico**, polityki i tak nie są egzekwowane (domyślny minikube ich nie wymusza) — więc albo
nic nie blokują, albo po przejściu na Calico nagle zaczynają. Nie włączaj full-lockdown na demo,
chyba że wystartowałeś `minikube start --cni=calico` i przetestowałeś.

---

## 7. Plan naprawy wg priorytetu

| # | Zadanie | Priorytet | Czas | Sekcja |
|---|---------|-----------|------|--------|
| 1 | Naprawić kodowanie skryptów (em-dash → `-`, zapis UTF-8 z BOM) | **Krytyczny** | 10 min | §5 |
| 2 | Ustalić tryb dostępu (tunnel **albo** port-forward) i opisać w README | **Krytyczny** | 15 min | §4 |
| 3 | Naprawić Loki (nazwa svc + `fullnameOverride: loki`, restart Grafany) | Wysoki | 20 min | §3 |
| 4 | Włączyć scrape cAdvisora (kubelet serviceMonitor) → panele CPU/RAM | Średni | 20 min | §2.3 |
| 5 | Kosmetyka: `or vector(0)` w panelu Error rate (5xx) | Niski | 5 min | §2.4 |
| 6 | Dopisać hint o `minikube tunnel` na końcu `deploy.ps1` | Niski | 5 min | §5.3 |

**Minimalna ścieżka na zaliczenie:** zrób 1 i 2. Reszta to dopieszczanie — panele CPU możesz pokazać
`kubectl top pods` + `minikube dashboard`, a logi przez `kubectl logs`.

---

## 8. Szybka checklista weryfikacji (po naprawach)

```powershell
# 1. Klaster i pody
minikube status
kubectl get pods -n forum-wedkarskie
kubectl get pods -n monitoring | Select-String "grafana|prometheus|loki|promtail"

# 2. Metryki kontenerów (po §2.3) — w Prometheus Targets kubelet = UP
kubectl top pods -n forum-wedkarskie

# 3. Loki (po §3) — nazwa svc i datasource test w Grafanie
kubectl get svc -n monitoring | Select-String "loki"

# 4. Dostęp (po §4)
minikube tunnel            # terminal osobny
curl http://forum.local/health/ready

# 5. Skrypty (po §5) — żaden nie ma em-dasha
Select-String -Path scripts\*.ps1 -Pattern ([char]0x2014)   # brak wyników = OK
```

---

## 9. Czego NIE powtarzać (z pamięci i docs/14, /15)

- ❌ `minikube delete` w trakcie aktywnego `minikube tunnel` → split-brain (docs/15). Fix: `reset-minikube.ps1 -NoPrompt`.
- ❌ Em-dashy / „smart quotes" w `.ps1`; ❌ zapis UTF-8 **bez** BOM (docs/14). Edytuj w VS Code, zapisuj UTF-8 z BOM.
- ❌ Zakładanie, że `forum.local`/NodePort działają na Windows bez tunelu — nie działają (docs/15).
- ❌ `full-lockdown/` bez Calico — albo nic nie robi, albo niespodziewanie blokuje po zmianie CNI.
- ❌ Reset DB po migracji bez `docker compose down -v` (dla Compose) / `reset-db.ps1` (dla K8s) — `DuplicateTable`.

---

*Koniec raportu. Jedyna zmiana w repo z tej sesji: utworzenie tego pliku (`docs/16-...`). Żaden kod ani manifest nie został zmodyfikowany — wszystkie naprawy są opisane jako instrukcje do wykonania.*
