# 17 — Audyt i naprawy: monitoring, bezpieczeństwo, startup

> **Cel.** Pełny audyt stanu na 2026-06-05 z **wykonanymi naprawami** (nie tylko diagnozą jak docs/16).
> Obejmuje: weryfikację wcześniejszych ustaleń, naprawę kodowania skryptów, naprawę monitoringu
> (cAdvisor / Loki / dashboard), audyt bezpieczeństwa z hardeningiem `SECRET_KEY`, oraz listę
> pozostałych luk z priorytetami.
>
> Data: 2026-06-05 · kod ~0.3.0 · **ten dokument opisuje zmiany, które już wprowadziłem w repo** (sekcja 1).

---

## 0. TL;DR — co naprawiłem, co zostaje

**Naprawione w tej sesji (kod/manifesty zmienione):**

| # | Zmiana | Plik |
|---|--------|------|
| 1 | Wszystkie 8 skryptów `.ps1` → **UTF-8 z BOM, czyste ASCII** (usunięte em-dashy `—` i polskie znaki) | `scripts/*.ps1` |
| 2 | Włączony scrape **kubelet/cAdvisor** → panele CPU/RAM podów przestają być „No data" | `values-kube-prometheus-stack.yaml` |
| 3 | **Loki**: `fullnameOverride: loki` → deterministyczna nazwa serwisu = URL datasource | `values-loki-stack.yaml` |
| 4 | Dashboard: panel „Error rate (5xx)" pokazuje **0** zamiast „No data"; datasource'y auto-bindują się do Prometheus/Loki | `grafana-dashboard-forum.yaml` |
| 5 | Naprawiony błędny alert `BackendDown` (`absent(up==1)` → poprawny idiom `max(up)==0`) | `prometheus-rules.yaml` |
| 6 | **Hardening `SECRET_KEY`**: fail-fast gdy domyślny klucz poza `DEBUG` | `backend/app/config.py` |
| 7 | `deploy.ps1`: jasny komunikat, że `forum.local` wymaga `minikube tunnel` | `scripts/deploy.ps1` |
| 8 | `install-monitoring.ps1`: kroki weryfikacji (kubelet target, nazwa Loki) | `scripts/install-monitoring.ps1` |

**Zostaje do zrobienia ręcznie (instrukcje w sekcji 5):** reinstalacja stacku monitoringu Helmem
(żeby zmiany 2-4 weszły w życie), ewentualnie Calico dla egzekucji NetworkPolicy, zmiana hasła Grafany.

---

## 1. Weryfikacja wcześniejszych ustaleń (docs/16)

Zanim cokolwiek zmieniłem, sprawdziłem fakty — część z docs/16 wymagała korekty:

| Teza z docs/16 | Werdykt po weryfikacji |
|----------------|------------------------|
| „highr histogram może nie istnieć (domyślny Instrumentator go nie emituje)" | **Błędne.** `prometheus-fastapi-instrumentator 7.1.0` emituje `http_request_duration_highr_seconds` domyślnie — panel p95 (9.839 ms) ma dane, co to potwierdza. Nie ruszam. |
| „Error rate 5xx = No data to nie błąd, tylko brak ruchu 5xx" | **Poprawne.** Naprawione kosmetycznie (`or vector(0)`). |
| „CPU/RAM No data = brak scrape cAdvisora" | **Poprawne.** Naprawione (sekcja 3). |
| „Loki: mismatch nazwy serwisu" | **Poprawne.** Naprawione `fullnameOverride`. |
| „Tylko port-forward = routing Windows, nie błąd sieci K8s" | **Poprawne.** Dodany hint o tunelu. |
| „Sekrety dev mogą być w repo" | **Sprawdzone — są bezpieczne.** `k8s/**/secret.yaml` są **gitignorowane** (`git check-ignore` potwierdza), w repo tylko `.example`. |

Wniosek: rdzeń diagnozy docs/16 był trafny; jedyna realna pomyłka to „highr" — dlatego warto było zweryfikować przed zmianą.

---

## 2. Naprawa skryptów PowerShell (kodowanie)

### Problem
Skany potwierdziły: `deploy.ps1`, `install-monitoring.ps1`, `portforward.ps1`, `run-load-test.ps1`,
`scaling-demo.ps1` miały znaki spoza ASCII (em-dash `—` U+2014 oraz `ę` w „Wędkarskie") w UTF-8
**bez BOM**. PowerShell 5.1 czyta takie pliki jako Windows-1250 → krzaki, a `—` w `Write-Host`
(`scaling-demo.ps1` l.20/31/40) potrafił wywalić skrypt. To dokładnie pułapka z docs/14.

### Naprawa (wykonana)
Każdy `.ps1`:
- zamiana `— – ‚ ' " " … nbsp` → odpowiedniki ASCII, polskie znaki → bez ogonków,
- zapis jako **UTF-8 z BOM** (PS 5.1 czyta poprawnie).

Weryfikacja — wszystkie 8 plików: `BOM=efbbbf`, `non-ASCII = 0`.

### Reguła na przyszłość
Skrypty `.ps1` trzymaj w **UTF-8 z BOM** (lub czystym ASCII). Żadnych em-dashy/smart-quotes.
Edytuj w VS Code („Save with Encoding → UTF-8 with BOM"). Komentarze najlepiej bez polskich ogonków.

---

## 3. Naprawa monitoringu

### 3.1. Panele CPU/RAM podów = „No data" (cAdvisor)
**Przyczyna:** dashboard pyta o `container_cpu_usage_seconds_total` / `container_memory_working_set_bytes`
— metryki z **cAdvisora (kubelet)**, których kube-prometheus-stack domyślnie na minikube nie scrapował.

**Naprawa (wykonana)** — dodane do `values-kube-prometheus-stack.yaml`:
```yaml
kubelet:
  enabled: true
  serviceMonitor:
    cAdvisor: true
```
To naprawia zarówno nasz panel „Backend CPU/memory by pod", jak i stockowe dashboardy
„Kubernetes / Compute Resources".

### 3.2. Loki nie działał
**Przyczyna:** datasource w Grafanie wskazuje `http://loki.monitoring.svc.cluster.local:3100`,
a chart `loki-stack` mógł nazwać serwis inaczej niż `loki`.

**Naprawa (wykonana)** — `values-loki-stack.yaml`:
```yaml
loki:
  fullnameOverride: loki   # gwarantuje serwis dokładnie "loki"
```
Po reinstalacji URL datasource jest pewny. (Jeśli `promtail` mimo to nie zbiera logów na minikube —
patrz docs/16 §3.3; na demo wystarczy `kubectl logs`.)

### 3.3. Dashboard „Forum Overview"
**Naprawy (wykonane)** w `grafana-dashboard-forum.yaml`:
- Panel „Error rate (5xx)": `... or vector(0) ...` → pokazuje **0%** zamiast „No data", gdy nie ma błędów.
- Zmienne datasource (`datasource`, `loki`) mają teraz `current` ustawione na `Prometheus`/`Loki`,
  więc panele bindują się automatycznie zamiast czekać na ręczny wybór źródła.

### 3.4. Błędny alert `BackendDown`
**Przyczyna:** `absent(up{...} == 1)` to anty-wzorzec — gdy `up` istnieje z wartością 0
(target zarejestrowany, ale Down), `up == 1` daje pusty wynik i `absent` zachowuje się myląco.

**Naprawa (wykonana)** w `prometheus-rules.yaml`:
```promql
(max(up{namespace="forum-wedkarskie", job="backend-service"}) or vector(0)) == 0
```
Pokrywa oba przypadki: „target Down" i „target zniknął".

---

## 4. Audyt bezpieczeństwa

### 4.1. Co jest dobre (potwierdzone w kodzie)
- **Sekrety**: `k8s/**/secret.yaml` gitignorowane; w repo tylko `.example`. `SECRET_KEY` w K8s z Secret `backend-secrets` (losowy 128-hex), nie z ConfigMap.
- **Hardening podów backendu**: `runAsNonRoot`, uid/gid 1000, `readOnlyRootFilesystem`, `allowPrivilegeEscalation:false`, `capabilities: drop ALL`, `seccompProfile: RuntimeDefault`.
- **Probes**: startup/liveness (proces) + readiness (`SELECT 1` → 503). Liveness nie dotyka DB (transient DB outage nie restartuje podów) — dobry wzorzec.
- **Security headers** (middleware): X-Frame-Options DENY, X-Content-Type-Options nosniff, HSTS, Referrer-Policy, CSP `default-src 'self'` (luźniejszy tylko dla Swaggera).
- **CORS**: jawne originy (nie `*`) — wymagane przy `allow_credentials`.
- **Upload**: whitelista MIME + sniffing + blokada wykonywalnych (`x-dosexec`, shellscript itd.), limit 25 MB.
- **`/metrics`**: NIE jest proxowane przez nginx frontendu → nie jest publiczne (brak information disclosure przez ingress).
- **NetworkPolicy**: DB tylko z podów `app: backend`.

### 4.2. Co naprawiłem
**`SECRET_KEY` — słaby default (luka #1 z docs/12).** `config.py` miał fallback
`"zmien-ten-klucz-na-produkcji"`. W K8s łatany Secretem, ale w Compose/lokalnie mógł zostać użyty.

**Naprawa (wykonana)** — walidator w `config.py`:
```python
@model_validator(mode="after")
def _reject_insecure_secret_key(self):
    if not self.DEBUG and self.SECRET_KEY == _INSECURE_SECRET_KEY:
        raise ValueError("SECRET_KEY ma domyslna, niebezpieczna wartosc...")
    return self
```
Aplikacja **odmawia startu**, jeśli poza `DEBUG` użyto domyślnego klucza. Zweryfikowane (pydantic 2.13):
- DEBUG=false + default → **raise** (blokada),
- DEBUG=true + default → start OK (dev),
- DEBUG=false + własny klucz → start OK (K8s/prod).

Nie psuje istniejących ścieżek: Compose ustawia własny `SECRET_KEY` + `DEBUG=true`; `.env.example`
ma `DEBUG=true`; K8s wstrzykuje klucz Secretem przy `DEBUG=false`.

### 4.3. Pozostałe luki (świadome, dev-only)
| Luka | Ryzyko | Rekomendacja |
|------|--------|--------------|
| Grafana `admin/admin` (`values-...stack.yaml`) | Niskie (dev, za port-forward) | Zmień `adminPassword` przed wystawieniem; na demo OK |
| MinIO `minioadmin/minioadmin`, NodePort 30900/30901 | Niskie (dev) | Rotacja przed shared deployment (`generate-secrets.ps1`) |
| Postgres `postgres/postgres` | Niskie (dev) | jw. |
| `REFRESH_COOKIE_SECURE: false`, ingress tylko HTTP | Średnie (prod) | TLS + cert-manager + cookie Secure dla prod (faza 9) |
| NetworkPolicy nieegzekwowana bez Calico | Informacyjne | `minikube start --cni=calico` jeśli chcesz pokazać egzekucję |
| `full-lockdown/` bez Calico | Pułapka | Nie włączać bez Calico (albo nic nie robi, albo zaskakuje po zmianie CNI) |

---

## 5. Co musisz zrobić, żeby naprawy weszły w życie

Zmiany w plikach `.ps1` i `config.py` działają od razu (następny start/build). **Zmiany w Helm
values (cAdvisor, Loki) wymagają reinstalacji stacku** — operator nie podmieni ich sam:

```powershell
# 1) Przeładuj kube-prometheus-stack (cAdvisor + dashboard)
helm upgrade monitoring prometheus-community/kube-prometheus-stack `
  --namespace monitoring -f k8s/monitoring/values-kube-prometheus-stack.yaml

# 2) Przeładuj Loki (pinned service name)
helm upgrade loki grafana/loki-stack `
  --namespace monitoring -f k8s/monitoring/values-loki-stack.yaml

# 3) Zastosuj poprawione obiekty aplikacji
kubectl apply -f k8s/monitoring/grafana-dashboard-forum.yaml
kubectl apply -f k8s/monitoring/prometheus-rules.yaml

# 4) (jeśli Grafana nie odświeży dashboardu od razu)
kubectl rollout restart deployment monitoring-grafana -n monitoring
```

Albo najprościej — odpal ponownie pełny instalator (robi to samo):
```powershell
.\scripts\install-monitoring.ps1
```

### Weryfikacja po reinstalacji
```powershell
kubectl top pods -n forum-wedkarskie                       # kubelet metryki żyją
kubectl get svc -n monitoring | findstr loki               # serwis = 'loki'
# Prometheus -> Status -> Targets : 'kubelet' i 'backend' = UP
# Grafana -> Forum Overview : panele CPU/RAM podów mają dane; Error rate = 0%
# Grafana -> Connections -> Data sources -> Loki -> Save & test = connected
```

---

## 6. Pełna analiza startupu (stan i ocena)

`scripts/deploy.ps1` jest **dobrze zbudowany i idempotentny** (wbrew docs/12, gdzie był opisany jako
niekompletny — został od tego czasu przepisany). Pokrywa: minikube + addony (ingress, metrics-server),
docker-env, build (opcjonalny), namespace + sekrety, postgres (z `-Clean` na wipe PVC), MinIO + bucket,
render configmap z IP minikube, migracje (z logami przy błędzie), workloady + HPA + PDB + cleanup,
frontend, NetworkPolicy, ingress, opcjonalny monitoring i lockdown. Czeka na `ready`/`complete` we
właściwych miejscach.

Drobne uwagi (nie naprawiałem — działają, to kwestia higieny):
- `portforward.ps1` używa `Start-Job` → output port-forwardów jest schowany; przy debugowaniu lepiej
  odpalać pojedyncze `kubectl port-forward` ręcznie. **pgAdmin już usunięty** (docs/12 był tu nieaktualny).
- `deploy.ps1 -Clean` usuwa PVC, ale nie czeka aktywnie na ich zniknięcie (jest `Start-Sleep 3`) —
  na wolnym dysku może być za krótko; w razie problemu powtórz deploy.

**Czy jest problem komunikacji w K8s?** Nie ma dowodów. Backend scrapuje się (panele RPS/latency),
HPA widzi metryki (6 replik), migracje przeszły (backend↔postgres OK). Objawy „No data"/„tylko
port-forward" miały inne źródła (cAdvisor, routing Windows), nie wewnętrzną sieć klastra.

---

## 7. Pozostałe niedociągnięcia (nie blokują zaliczenia)

| Temat | Priorytet | Uwaga |
|-------|-----------|-------|
| Reinstalacja Helm (sekcja 5) | **Wymagane** by naprawy 2-4 zadziałały | 5 min |
| Hasło Grafany / rotacja sekretów dev | Niski | przed shared/grading |
| TLS / cert-manager / cookie Secure | Niski (dev), wysoki (prod) | faza 9 |
| Calico (egzekucja NetworkPolicy) | Opcjonalny | tylko jeśli chcesz to pokazać |
| Promtail na minikube (jeśli puste logi w Loki) | Niski | docs/16 §3.3; `kubectl logs` wystarcza |
| `pytest`/`ruff`/`mypy` (slug PL, ostrzeżenia) | Python | docs/10; nie dotyczy K8s |
| CI/CD (`kubectl --dry-run`, pytest w Actions) | Faza 9 | brak |

---

## 8. Pułapki, których NIE powtarzać (zaktualizowane)

- ❌ `minikube delete` w trakcie `minikube tunnel` → split-brain. Fix: `reset-minikube.ps1 -NoPrompt`. (docs/15)
- ❌ Em-dashy / smart-quotes w `.ps1`; ❌ UTF-8 **bez** BOM. **Naprawione — trzymaj UTF-8 z BOM.** (docs/14)
- ❌ Zakładanie, że `forum.local`/NodePort działają na Windows bez `minikube tunnel`. (docs/15)
- ❌ `absent(up == 1)` jako „target down" — używaj `max(up)==0`. **Naprawione.**
- ❌ Dashboardy CPU/RAM bez włączonego scrape cAdvisora. **Naprawione w values.**
- ❌ **Mount-lag** (docs/CLAUDE.md): po edycji pliku sandbox/bash może chwilę widzieć starą/uciętą
  wersję — to potwierdziło się w tej sesji przy `config.py`. **Ufaj narzędziu Read, nie `cat`/`wc`.**
- ❌ Domyślny `SECRET_KEY` poza DEBUG — **teraz blokowany walidatorem.**

---

*Koniec. Zmiany w repo z tej sesji: `scripts/*.ps1` (kodowanie), `k8s/monitoring/{values-kube-prometheus-stack,values-loki-stack,grafana-dashboard-forum,prometheus-rules}.yaml`, `backend/app/config.py`, `scripts/{deploy,install-monitoring}.ps1`, oraz ten dokument. Wymagany krok ręczny: reinstalacja Helm (sekcja 5).*
