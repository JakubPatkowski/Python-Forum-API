# 10 — Raport stabilizacji i zamknięcia projektu

> **Cel raportu.** Pełna analiza tego, co trzeba dokończyć, żeby zamknąć projekt
> i zaliczyć **dwa przedmioty**: *Zaawansowane programowanie w Python* (backend)
> oraz zajęcia z **Kubernetesa** (orkiestracja, skalowanie, monitoring, testy).
> Zakres celowo **bez WebSocketa i bez dużych nowych funkcji** — koncentrujemy się
> na stabilizacji, brakach „okołozaliczeniowych" i zgłoszeniu luk bezpieczeństwa.
>
> Data: 2026-06-03 · wersja kodu 0.3.0 · autor analizy: sesja Cowork
> Plik niczego nie zmienia w kodzie — to raport i lista zadań. Decyzja, co
> wdrażać, należy do Ciebie.

---

## 0. TL;DR — werdykt

| Obszar | Stan | Czy blokuje zaliczenie |
|--------|------|------------------------|
| Backend — architektura i zakres funkcji | **Dobry** (Clean Arch, modular monolith, 5 modułów, 111 testów) | Nie |
| Backend — higiena (lint/typy/testy „green") | **Rozjazd z deklaracją w CLAUDE.md** — 1 test FAIL, ~133 błędy ruff, 145 błędów mypy | Częściowo (jeśli prowadzący patrzy na jakość) |
| Kubernetes — podstawy (deploy, service, PVC, Job, CronJob) | **Dobry** | Nie |
| Kubernetes — skalowanie / monitoring / testy | **Brakuje całkowicie** (brak HPA, brak Prometheus/Grafana, brak testów k8s) | **TAK** — to jest sedno przedmiotu o k8s |
| Bezpieczeństwo | **Kilka poważnych luk** (klucz JWT w ConfigMap, domyślne hasła, brak securityContext/NetworkPolicy) | Nie blokuje, ale **trzeba zgłosić i opisać** |

**Najkrótsza droga do zaliczenia obu przedmiotów** jest w sekcji 6 (plan 3-dniowy).

---

## 1. Co jest realnie gotowe (nie ruszamy)

Backend jest najmocniejszą częścią i faktycznie jest „w miarę dopracowany":

- **Clean Architecture / modular monolith** — reguła zależności `domain ← application ← infrastructure/presentation` jest przestrzegana; logika w `use_cases/`, routery cienkie.
- **5 modułów**: `identity` (JWT access+refresh, rotacja, reuse-detection, RBAC+ACL, Argon2id), `content` (posty/komentarze z materialized path, FTS, keyset pagination), `files` (MinIO, miniatury, sprzątanie sierot), `engagement` (polubienia + widok `user_stats`), + szkielety `notifications`/`audit`.
- **Migracje Alembic** 0001–0009 (koniec z `create_all`), z guardem na starym wolumenie.
- **Docker multi-stage** z `uv`, non-root uid 1000, slim runtime — porządny obraz.
- **K8s podstawy**: namespace, Deploymenty, Service, PVC, **migration-Job**, **cleanup-CronJob**, ConfigMap/Secret split. To już jest powyżej poziomu „minimum".
- **111 testów jednostkowych przechodzi** (z 112), pokrycie obejmuje wartości domenowe, JWT, ścieżki komentarzy, paginację, agregat plików.

To wszystko zostaje. Poniżej tylko to, co wymaga domknięcia.

---

## 2. Backend — co dokończyć dla przedmiotu z Pythona

### 2.1. Higiena jakości — deklaracja vs rzeczywistość ⚠️

`CLAUDE.md` deklaruje: *„`mypy --strict`, ruff (E,F,I,B,UP,N,S,ASYNC,SIM,C4)"* oraz że kod jest czysty. **Tak nie jest** — uruchomiłem narzędzia:

| Narzędzie | Wynik | Komentarz |
|-----------|-------|-----------|
| `pytest tests/unit` | **1 failed, 110 passed** | patrz 2.2 |
| `ruff check app` | **133 błędy** (97 auto-fix `--fix`) | gł. `I001` sortowanie importów (~48), `N818` nazwy wyjątków bez sufiksu `Error` (~25), `F401` nieużyte importy, `E501` długość linii |
| `ruff check tests` | 4 błędy (wszystkie auto-fix) | drobne |
| `mypy app` | **145 błędów w 30 plikach** | brak parametrów generycznych (`EntityId`, `list`), nieanotowane funkcje w `content/infrastructure/mappers.py`, niezgodność typów w `files/.../image_processing.py:43` |

To nie są błędy logiczne, ale dla przedmiotu o **zaawansowanym Pythonie** „green CI" to często warunek oceny. Większość ruffa znika po `ruff check app --fix`; reszta (`N818`, mypy) to kilka godzin ręcznej roboty.

**Rekomendacja:** albo doprowadzić do zera (`ruff --fix` + ręczne mypy), albo — jeśli czas goni — **urealnić deklarację** w `CLAUDE.md`/README, żeby nie obiecywać czegoś, czego kod nie spełnia. Najgorszy wariant to rozjazd dokumentacji z kodem zauważony przez prowadzącego.

### 2.2. Realny bug: slug gubi polskie znaki 🐛

Test `test_value_objects.py::TestSlug::test_from_text_strips_accents_and_lowercases` **failuje**. `Slug.from_text("Łódź Łowienie")` produkuje `odz-owienie` zamiast `lodz-lowienie`:

- `unicodedata.normalize("NFKD", …)` rozkłada `ó→o`, ale **`ł` (U+0142) nie ma dekompozycji NFKD** — zostaje, a potem regex `[^a-z0-9]` zamienia je na `-` i `strip("-")` usuwa.
- Efekt: słowa złożone tylko z polskich liter mogą dać **pusty albo okaleczony slug** — a to jest *forum wędkarskie po polsku*.

Wpływ jest ograniczony (adresowanie idzie po `public_id` UUID, slug jest kosmetyczny), ale to widoczny, łatwy do pokazania błąd. Fix: mapa transliteracji PL (`ł→l, ż→z, ź→z, ń→n, …`) przed NFKD, albo poprawić sam test, jeśli świadomie rezygnujemy z transliteracji. **Nie zostawiać failującego testu** — to pierwsza rzecz, którą widać po `pytest`.

### 2.3. Legacy island do sprzątnięcia

`pyproject.toml` wciąż ciągnie **`python-jose` + `passlib[bcrypt]`** („legacy auth") obok docelowego `pyjwt` + `argon2`. Żywe pozostałości:

- `app/core/security.py` — bcrypt + jose, używane przez admin SSR (`/admin`) i część legacy.
- `app/routers/{auth,users,posts,comments,categories}` — **istnieją, ale nie są montowane** (martwy kod).
- `app/services/`, `app/schemas/` — legacy.

Dwie ścieżki uwierzytelniania (jose dla admina, pyjwt dla API) to jednocześnie **dług techniczny i powierzchnia ataku**. Na zamknięcie projektu: albo usunąć martwe routery i zmigrować admin SSR na `pyjwt`/`argon2` (czysto), albo przynajmniej **udokumentować świadomie**, że admin SSR to osobny, legacy moduł. Usunięcie nieużywanych routerów to niskie ryzyko i ładnie odchudza repo.

### 2.4. `/health/ready` to atrapa

```python
@app.get("/health/ready")
def health_ready(): return {"status": "ready"}   # TODO(phase 4)
```

Endpoint **zawsze** zwraca „ready", nie sprawdzając bazy. To podwójny problem: (a) Kubernetes nie odetnie ruchu od poda, który stracił DB; (b) backend Deployment i tak go nie używa (patrz 3.3). Minimalny fix: `SELECT 1` na sesji DB + zwróć 503, gdy pada. To 10 linijek, a robi dobre wrażenie przy omawianiu „readiness vs liveness" na obronie.

### 2.5. Async-over-sync (znane, do świadomej decyzji)

Repozytoria są `async def` na **synchronicznym** `Session` SQLAlchemy — czyli blokują event loop. Przy obciążeniu projektu studenckiego to nie boli, ale warto **świadomie odnotować** (decyzja D1 z `docs/07`), bo na przedmiocie z zaawansowanego Pythona pytanie „dlaczego async repo na sync sesji?" jest bardzo prawdopodobne. Nie trzeba przepisywać — trzeba umieć obronić.

---

## 3. Kubernetes — to jest serce drugiego przedmiotu ⭐

Tu jest największa luka względem Twoich celów („skalowanie, monitoring, statystyki, testy k8s"). Obecny `k8s/` to poprawny **deploy**, ale brakuje wszystkiego, co przedmiot o orkiestracji zwykle ocenia.

### 3.1. Brak autoskalowania (HPA) — must-have

- **Nie ma żadnego `HorizontalPodAutoscaler`.** Backend ma na sztywno `replicas: 1`. Co ciekawe, `migration-job.yaml` w komentarzu zakłada `kubectl apply -f k8s/backend/  # deployment, service, hpa, ...` — czyli HPA był w planie, ale pliku nie ma.
- Backend ma już ustawione `resources.requests/limits` (cpu 100m–500m) — czyli HPA na CPU zadziała od ręki.

**Do zrobienia:** `k8s/backend/hpa.yaml` (np. `minReplicas: 2`, `maxReplicas: 6`, target CPU 70%). Na minikube wymaga włączenia **metrics-server**: `minikube addons enable metrics-server`. Demo skalowania (np. `hey`/`ab` na `/api/v1/posts` i pokazanie `kubectl get hpa -w`) to klasyczny element zaliczenia.

### 3.2. Brak monitoringu — Prometheus/Grafana

- Backend **eksponuje `/metrics`** (`prometheus-fastapi-instrumentator` jest wpięty w `main.py`) — czyli połowa pracy zrobiona.
- Ale w `k8s/` **nie ma nic** do zbierania tych metryk: brak `k8s/monitoring/`, brak `ServiceMonitor`, brak Prometheusa, brak Grafany, brak dashboardu. `docs/07` opisuje to jako „Fazę 7", ale faza nie została wykonana.

**Do zrobienia (minimum na zaliczenie):**
1. `kube-prometheus-stack` przez Helm w ns `monitoring` (Prometheus + Grafana w jednym).
2. `ServiceMonitor` (albo annotacje `prometheus.io/scrape`) celujący w `backend-service:8000/metrics`.
3. Jeden dashboard „Forum Overview": request rate, error rate, p95 latency, liczba replik (powiązanie z HPA). Można zaimportować gotowy dashboard FastAPI i podmienić źródło.

To dokładnie pokrywa Twoje „monitorował jakieś statystyki".

### 3.3. Probe wskazuje zły endpoint

Backend Deployment używa **`/health`** zarówno dla readiness, jak i liveness:

```yaml
readinessProbe: { httpGet: { path: /health, port: 8000 } }
livenessProbe:  { httpGet: { path: /health, port: 8000 } }
```

`/health` zawsze zwraca 200 bez sprawdzania niczego. Powinno być: **liveness → `/health/live`**, **readiness → `/health/ready`** (po naprawie z 2.4, żeby ready realnie sprawdzał DB). Inaczej readiness nie spełnia swojej roli. To drobna zmiana z dużym znaczeniem dydaktycznym.

### 3.4. Brak limitów i probe'ów na pozostałych komponentach

Niespójność, którą prowadzący wyłapie od razu:

| Komponent | resources | readiness/liveness | securityContext |
|-----------|-----------|--------------------|-----------------|
| backend | ✅ | ⚠️ zły endpoint | ❌ brak |
| minio | ✅ | ✅ | ❌ brak |
| **postgres** | ❌ brak | ❌ brak | ❌ brak |
| **frontend** | ❌ brak | ❌ brak | ❌ brak |
| **pgadmin** | ❌ brak | ❌ brak | ❌ brak |

Postgres bez `resources` i bez probe'a to najpoważniejszy z tych braków (najważniejszy stateful komponent). Dodanie `requests/limits` + `readinessProbe` (`pg_isready` / TCP 5432) i frontendowi `readinessProbe` na `/` to godzina pracy, a domyka „dobre praktyki k8s".

### 3.5. Brak hardeningu k8s

Pod kątem zarówno przedmiotu, jak i bezpieczeństwa brakuje:

- **`securityContext`** w żadnym podzie (`runAsNonRoot: true`, `runAsUser: 1000`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`). Obraz backendu **już** ma użytkownika 1000 — wystarczy go „przypiąć" w manifeście (Dockerfile to wręcz sugeruje w komentarzu).
- **`NetworkPolicy`** — brak. Domyślnie wszystko gada ze wszystkim. `docs/07` faza 8 to opisuje. Choćby jedna polityka (postgres przyjmuje ruch tylko od `app=backend`) to świetny materiał na demo.
- **`PodDisruptionBudget`** — brak (przy HPA z `minReplicas: 2` warto `minAvailable: 1`).
- **`Ingress`** — brak; wejście tylko przez NodePort (frontend `30080`, MinIO `30900`). Dla minikube to OK, ale Ingress + host `forum.local` wygląda dojrzalej.

### 3.6. Brak testów Kubernetesa

Mówisz wprost: „testy kubernetesa". Obecnie **nie ma żadnych**. Opcje (od najtańszej):

1. **Walidacja manifestów statycznie** — `kubeconform` albo `kubectl apply --dry-run=server -f k8s/` w CI. Tanio, robi dobre wrażenie.
2. **Smoke test po deployu** — skrypt, który czeka na `kubectl rollout status`, odpytuje `/health/ready`, `/api/v1/categories`, i sprawdza, czy `kubectl get hpa` istnieje. PowerShell-owy `scripts/deploy.ps1` można rozbudować o sekcję `Test`.
3. **Test skalowania** — wygeneruj obciążenie, pokaż wzrost replik (manualnie lub skryptem). To jest „test k8s", którego najczęściej oczekują na takim przedmiocie.

### 3.7. Drobiazg konfiguracyjny: `MINIO_PUBLIC_ENDPOINT`

W `k8s/backend/configmap.yaml` jest literalnie `MINIO_PUBLIC_ENDPOINT: "<minikube-ip>:30900"`. Jeśli nie podmienisz `<minikube-ip>` na wynik `minikube ip`, presigned URL-e do plików **nie zadziałają z przeglądarki**. To częsta „działa-u-mnie-nie-działa-na-obronie" pułapka — warto albo zautomatyzować podmianę w `deploy.ps1`, albo opisać w instrukcji uruchomienia.

---

## 4. Bezpieczeństwo — luki do zgłoszenia 🔒

Zgodnie z prośbą — poważniejsze znaleziska. Sortowane wg istotności. To projekt studencki na minikube, więc większość to „nie rób tak na produkcji", ale **świadome wymienienie ich w raporcie samo w sobie jest wartością na obronie**.

### 4.1. Klucz JWT w ConfigMap, w repozytorium — POWAŻNE

`k8s/backend/configmap.yaml` (plik **śledzony w git**) zawiera:

```yaml
SECRET_KEY: "change-me-via-secret"
```

Backend Deployment robi `envFrom: configMapRef: backend-config` i **nie montuje** `backend-secrets` (istnieje tylko `secret.example.yaml`, prawdziwy nigdy nie wpięty). Skutki:

- Tokeny JWT są podpisywane **przewidywalnym, jawnym** kluczem z repo → każdy, kto widzi repo, może **sfałszować dowolny token** (np. admina).
- Defaultem w `config.py` jest `"zmien-ten-klucz-na-produkcji"` — równie słaby. Testy zresztą krzyczą `InsecureKeyLengthWarning: HMAC key is 10 bytes`.

**Fix:** wygenerować `openssl rand -hex 64`, włożyć do `k8s/backend/secret.yaml` (już gitignorowany), dopiąć `secretRef: backend-secrets` w Deployment, usunąć `SECRET_KEY` z ConfigMap. To jest **najważniejsza** pojedyncza poprawka bezpieczeństwa.

### 4.2. Domyślne / słabe hasła wszędzie

- **Postgres**: `postgres/postgres` (configmap DSN + secret).
- **MinIO**: `minioadmin/minioadmin` (root + access/secret).
- **pgAdmin**: `admin@forum.pl / admin`.

Sekrety k8s (`secret.yaml`) są gitignorowane (dobrze), ale wartości to domyślne stałe. Na minikube to akceptowalne — ale **trzeba to nazwać w raporcie** jako „dev-only credentials, do rotacji przed produkcją". Plus: w `docker-compose.yml` te same hasła są jawnie (to dev, OK).

### 4.3. pgAdmin w klastrze aplikacyjnym

`pgadmin` w ns `forum-wedkarskie`, bez `resources`, bez probe'a, bez NetworkPolicy, z `admin/admin`. To pełnoprawne narzędzie administracyjne do bazy wystawione obok aplikacji. Dla zaliczenia: albo wyrzucić z domyślnego deployu (uruchamiać ad-hoc), albo przynajmniej odciąć NetworkPolicy i zmienić hasło. Narzędzia debugowe nie powinny domyślnie jechać z aplikacją.

### 4.4. `REFRESH_COOKIE_SECURE = False`

Refresh token (cookie httpOnly) ma `Secure=False` domyślnie. Bez HTTPS cookie leci czystym tekstem. Dla lokalnego minikube po HTTP to wymuszone, ale jeśli wystawiasz Ingress z TLS — przełącz na `True`. Warto sterować tym przez env per-środowisko.

### 4.5. `latest` w obrazach infrastruktury

`minio/minio:latest`, `dpage/pgadmin4:latest`, `postgres:16-alpine` (ten OK). `:latest` = niedeterministyczny deploy i brak kontroli nad CVE. Przypiąć konkretne tagi/digesty. Drobne, ale to klasyk „dobrych praktyk".

### 4.6. Pozytywy (warto wymienić w raporcie jako mocne strony)

- **Argon2id** na hasła w docelowym module, JWT z rotacją refresh + **reuse-detection**, RBAC + per-user ACL.
- **SecurityHeadersMiddleware** (HSTS/CSP/X-Frame-Options) i **LimitUploadSizeMiddleware** (411/413).
- **Walidacja uploadów**: whitelist MIME + sniffing `python-magic` + blokowanie wykonywalnych/HTML.
- **CORS** z jawnymi originami (nie wildcard) przy `allow_credentials`.
- **SQL w module `engagement`** jest surowy (`text()`), ale **poprawnie parametryzowany**; `target_type` z whitelisty, klauzule statyczne — **brak SQL injection**. Sprawdzone.
- Markdown renderowany przez `markdown-it` + **DOMPurify** → ochrona przed XSS.

To solidny fundament — luki są głównie „operacyjne" (sekrety, hardening), nie w samej logice aplikacji.

---

## 5. Lista zbiorcza znalezisk (priorytety)

| # | Znalezisko | Obszar | Priorytet | Szac. nakład |
|---|-----------|--------|-----------|--------------|
| 1 | `SECRET_KEY` w ConfigMap, `backend-secrets` niepodpięty | Bezpieczeństwo | **Krytyczny** | 30 min |
| 2 | Brak HPA + metrics-server | K8s | **Wysoki** (sedno przedmiotu) | 1–2 h |
| 3 | Brak Prometheus/Grafana (mimo `/metrics`) | K8s | **Wysoki** | 2–4 h |
| 4 | Failujący test slug (PL znaki) | Python | **Wysoki** (widać po `pytest`) | 30–60 min |
| 5 | 145 mypy + 133 ruff vs deklaracja „clean" | Python | Wysoki | 2–5 h |
| 6 | Probe backendu → zły endpoint; `/health/ready` to atrapa | K8s + Python | Wysoki | 30 min |
| 7 | Brak testów k8s (dry-run + smoke) | K8s | Średni | 1–2 h |
| 8 | Postgres/frontend/pgadmin bez resources/probe | K8s | Średni | 1 h |
| 9 | Brak securityContext / NetworkPolicy / PDB | K8s + Bezp. | Średni | 1–2 h |
| 10 | Domyślne hasła (pg/minio/pgadmin) + pgadmin w klastrze | Bezpieczeństwo | Średni | 30 min + opis |
| 11 | Legacy island (jose/passlib, niemontowane routery) | Python | Niski | 1–3 h |
| 12 | `MINIO_PUBLIC_ENDPOINT` placeholder; obrazy `:latest`; cookie `Secure` | K8s/Bezp. | Niski | 30 min |

---

## 6. Plan domknięcia — realistyczny, ~3 sesje

Kolejność dobrana tak, by **najpierw zabezpieczyć zaliczenie obu przedmiotów**, potem kosmetyka.

### Sesja A — „zielony backend" (przedmiot z Pythona)
1. Napraw failujący test slug (#4) — transliteracja PL lub korekta testu.
2. `ruff check app --fix`, potem ręcznie domknij resztę; przejedź mypy (#5). Cel: `pytest`, `ruff`, `mypy` na zielono **albo** urealnij deklarację w `CLAUDE.md`.
3. `/health/ready` z realnym `SELECT 1` (#6, część backendowa).
4. (Opcjonalnie) usuń niemontowane legacy routery (#11) — szybkie odchudzenie.

### Sesja B — „k8s, który skaluje i monitoruje" (przedmiot z k8s) ⭐
1. `minikube addons enable metrics-server`; dodaj `k8s/backend/hpa.yaml` (2–6, CPU 70%) (#2).
2. Popraw probe backendu: liveness→`/health/live`, readiness→`/health/ready` (#6).
3. Dodaj `resources` + readiness do postgresa i frontendu (#8).
4. Wdróż `kube-prometheus-stack` + ServiceMonitor na `/metrics` + 1 dashboard Grafany (#3).
5. Demo: obciążenie → `kubectl get hpa -w` pokazuje wzrost replik; Grafana pokazuje ruch. **To jest gotowy materiał na obronę.**

### Sesja C — hardening + testy + bezpieczeństwo
1. Wpnij `backend-secrets` z mocnym `SECRET_KEY`, usuń go z ConfigMap (#1).
2. `securityContext` (runAsNonRoot/1000) na podach; jedna `NetworkPolicy` (postgres ← tylko backend); `PodDisruptionBudget` (#9).
3. `scripts/deploy.ps1`: sekcja `Test` — `kubectl apply --dry-run=server` + smoke na `/health/ready` i `/api/v1/categories` (#7).
4. Zmień hasło pgAdmina lub wyłącz go z domyślnego deployu; przypnij tagi obrazów; `REFRESH_COOKIE_SECURE` per-env (#10, #12).
5. Zaktualizuj `MINIO_PUBLIC_ENDPOINT` (auto-podmiana w deploy.ps1) (#12).

Po tych trzech sesjach masz: zielony backend (Python), klastr który **skaluje się i ma dashboard** (k8s), oraz zamknięte luki bezpieczeństwa — czyli pełne pokrycie obu przedmiotów + porządny raport bezpieczeństwa do dołączenia.

---

## 7. Czego świadomie NIE robimy

Zgodnie z Twoją decyzją o stabilizacji, **poza zakresem**: WebSocket (faza 5), RabbitMQ + `notifications`/`audit` (faza 4), prezigned-upload UI, „moje pliki", odświeżanie wygasłych URL-i, tworzenie tagów w UI. Te moduły zostają jako szkielety — to jest OK i spójne z „zamykam projekt". Warto tylko w README dopisać jedno zdanie, że to świadomie odłożony scope, a nie niedokończona robota.

---

*Raport wygenerowany na podstawie analizy kodu (uruchomione: `pytest`, `ruff`, `mypy`), manifestów `k8s/`, `docker-compose.yml`, `Dockerfile` oraz dokumentów `docs/01–09`. Żaden plik źródłowy nie został zmieniony.*
