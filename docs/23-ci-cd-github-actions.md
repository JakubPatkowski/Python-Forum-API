# 23 — CI/CD: GitHub Actions (Faza 9)

Kompletny pipeline CI/CD oparty o GitHub Actions. Wszystkie workflow są w
`.github/workflows/`. Zaprojektowane pod **brak jakichkolwiek powiadomień**
(maile, komentarze na PR, czaty) — wyniki trafiają wyłącznie do zakładek
*Actions* / *Security* / *Pages* repozytorium.

## Przegląd workflow

| Plik | Co robi | Wyzwalacze |
|------|---------|-----------|
| `ci-backend.yml` | Ruff (lint+format), mypy `--strict`, pytest (unit + integration na testcontainers), pokrycie → Codecov | push/PR `backend/**`, ręcznie |
| `ci-frontend.yml` | pnpm `--frozen-lockfile`, ESLint, build Vite, artefakt `dist` | push/PR `frontend/**`, ręcznie |
| `docker-build.yml` | Build obrazów backend+frontend (Buildx, cache GHA) i push do **ghcr.io** | push `master`/tag `v*`, PR (tylko build), ręcznie |
| `codeql.yml` | SAST CodeQL dla Pythona i JS/TS (`security-extended`) → SARIF | push/PR `master`, co tydzień, ręcznie |
| `security.yml` | Trivy (zależności + sekrety + IaC) oraz Gitleaks (historia git) → SARIF | push/PR `master`, co tydzień, ręcznie |
| `api-docs.yml` | Eksport `openapi.json` → statyczny Redoc → publikacja na **GitHub Pages** | push `master` `backend/**`, ręcznie |
| `e2e-kind.yml` | Efemeryczny klaster **kind**, deploy realnych manifestów `k8s/`, smoke test (health + register/login) | push/PR `backend|frontend|k8s/**`, ręcznie |
| `performance.yml` | Stack przez docker compose + **k6** (profil `smoke`); progi p95/error-rate jako bramka regresji | push/PR `backend|load/**`, ręcznie |

Wspólne dobre praktyki w każdym workflow:

- **Najmniejsze uprawnienia** — domyślnie `permissions: contents: read`,
  podnoszone tylko tam, gdzie trzeba (`packages: write`, `security-events:
  write`, `pages: write` / `id-token: write`).
- **`concurrency`** — anuluje nadpisane runy na tym samym refie (oszczędność
  minut CI).
- **Filtry ścieżek** — workflow odpala się tylko, gdy zmienił się odpowiedni
  obszar repo.
- **`workflow_dispatch`** — każdy można uruchomić ręcznie (wygodne na demo).
- **Wersje akcji** przypięte do majorów (`@v4`, `@v6`, …); do dalszego
  hardeningu można przypiąć do konkretnego SHA.

## Konfiguracja jednorazowa w repozytorium

1. **GitHub Pages** (dla `api-docs.yml`): *Settings → Pages → Build and
   deployment → Source = **GitHub Actions***.
2. **Code scanning / SARIF** (`codeql.yml`, `security.yml`): działa out-of-the-box
   dla repozytoriów **publicznych**. Dla prywatnych wymaga GitHub Advanced
   Security. Wyniki: zakładka *Security → Code scanning*.
3. **GHCR** (`docker-build.yml`): używa wbudowanego `GITHUB_TOKEN` — nie trzeba
   żadnych sekretów. Po pierwszym pushu obrazy pojawią się w *Packages*. Aby były
   publiczne: *Package settings → Change visibility → Public*. Obrazy:
   `ghcr.io/jakubpatkowski/python-forum-api-backend` i `…-frontend`.
4. **Codecov** (`ci-backend.yml`): dla repo publicznego działa bez tokenu.
   Opcjonalnie dodaj sekret `CODECOV_TOKEN` (*Settings → Secrets and variables →
   Actions*). Upload nigdy nie wywala builda (`fail_ci_if_error: false`).

## Brak powiadomień — gdzie to ustawić

Workflow **nie wysyłają** żadnych maili/komentarzy. Pozostałe źródła powiadomień
to ustawienia **konta GitHub**, nie pliki YAML — wyłącz je u siebie:

- *Settings → Notifications* → sekcja **Actions**: odznacz „Send notifications
  for failed workflows…”.
- Alerty Code scanning / Dependabot: *Settings → Notifications* (lub
  *Watch → Custom* na repo) — wycisz, jeśli nie chcesz maili o nowych
  znaleziskach (same znaleziska i tak są widoczne w zakładce Security).
- Codecov: `codecov.yml` ma `comment: false` i statusy `informational: true`
  (raportuje, nigdy nie blokuje ani nie komentuje).

Świadomie **nie dodano Dependabota** (generowałby PR-y i maile).

## Szczegóły i decyzje projektowe

### Backend — testy i pokrycie
Job `test` instaluje `libmagic1` (runtime dla `python-magic`), robi `uv sync`,
a następnie uruchamia w **dwóch osobnych procesach**:

1. `pytest -m "not integration"` — testy jednostkowe + „in-memory” (files),
2. `pytest tests/integration/identity -m integration` — pełny flow auth na realnym
   Postgresie przez **testcontainers**.

Rozdzielenie jest celowe: test integracyjny ustawia `DATABASE_URL` dopiero w
fixture i robi *późny import* `create_app`. Gdyby w tym samym procesie zebrać moduł
testów `files` (importuje `app.config` na poziomie modułu), singleton `settings`
zostałby „zamrożony” z domyślnym DSN i kontener nie zostałby użyty. Dlatego krok
integracyjny jest zawężony do katalogu `identity`. Pokrycie z obu przebiegów
łączymy (`--cov-append`) i wysyłamy do Codecov.

Zmienne środowiskowe ustawione na poziomie joba (`DEBUG=true`, `SECRET_KEY`,
`UPLOAD_DIR=/tmp/...`) są wymagane, bo `create_app()` wykonuje się przy imporcie:
walidator odrzuca domyślny `SECRET_KEY` poza `DEBUG`, a aplikacja tworzy katalog
`UPLOAD_DIR` (domyślne `/app/uploads` nie jest zapisywalne na runnerze).

### Frontend — lint + reprodukowalny build
Dodano `frontend/pnpm-lock.yaml` (instalacje `--frozen-lockfile`) oraz ESLint 9
(flat config, `eslint.config.js`). `react-in-jsx-scope` wyłączone (automatyczny
JSX runtime Vite). `no-unused-vars` nie zgłasza nieużywanych argumentów (props),
żeby nie psuć API komponentów. Usunięto realny martwy kod (nieużywana funkcja
`initials`, zbędny `const t`).

### Obrazy Docker → GHCR
`docker/metadata-action` generuje bogaty zestaw tagów (branch, PR, semver z tagów
git, krótki SHA, `latest` na gałęzi domyślnej). PR-y tylko budują (bez pushu).
Cache warstw przez `type=gha`. `provenance: false` — czystsze manifesty w
Packages.

### Bezpieczeństwo (SAST + zależności + sekrety)
Trzy warstwy, wszystkie raportują przez **SARIF** do zakładki Security:

- **CodeQL** — natywny SAST GitHuba (Python + JS/TS), zestaw `security-extended`.
- **Trivy** — podatności zależności (`uv.lock`, `pnpm-lock.yaml`), sekrety oraz
  błędy konfiguracji IaC (Dockerfile + manifesty k8s).
- **Gitleaks** — skan sekretów w całej historii git (`fetch-depth: 0`).

Trivy i Gitleaks uruchamiamy z **oficjalnego skryptu/obrazu** (nie z akcji z
Marketplace). To celowe: w marcu 2026 tagi akcji `aquasecurity/*` zostały
skompromitowane (atak na łańcuch dostaw). Oba narzędzia działają z
`--exit-code 0` — nie blokują builda, dają tylko widoczność. Dla pełnego
hardeningu warto przypiąć wersję narzędzia i sprawdzać sumę kontrolną.

### API docs → GitHub Pages
`backend/scripts/export_openapi.py` importuje aplikację i zrzuca `app.openapi()`
do `openapi.json` (bez bazy). Redoc (`@redocly/cli build-docs`) renderuje
statyczny `index.html`, który `actions/deploy-pages` publikuje na Pages.

### E2E na efemerycznym klastrze kind
To „środowisko staging” projektu: każdy run tworzy klaster `kind`, ładuje do
niego zbudowane obrazy (`kind load docker-image`, `imagePullPolicy: Never`) i
wdraża **te same manifesty z `k8s/`**, co minikube. Realne sekrety są w
`.gitignore`, więc workflow generuje dev-owe sekrety w locie (hasło Postgresa
musi pasować do `DATABASE_URL` z `backend-config`). Kolejność: namespace →
sekrety → Postgres → MinIO → Job migracji → backend → frontend. Następnie smoke
(`scripts/e2e-smoke.sh`) przez `port-forward`: health/live, health/ready (DB),
publiczny odczyt oraz register+login. Przy porażce zrzucane są pody, eventy i
logi.

### Regresja wydajności (k6)
`docker compose up` podnosi stack, potem k6 (obraz `grafana/k6`, `--network
host`) uruchamia profil `smoke` z `load/k6-load-test.js`. Profil ma progi
(`p(95) < 800 ms`, `errors < 1%`); ich przekroczenie kończy joba błędem = wykryta
regresja. Podsumowanie JSON ląduje jako artefakt (30 dni).

## Lokalna walidacja
```bash
# Lint wszystkich workflow (jak na CI):
actionlint .github/workflows/*.yml

# Frontend:
cd frontend && pnpm install --frozen-lockfile && pnpm run lint && pnpm run build

# Eksport OpenAPI:
cd backend && DEBUG=true uv run python scripts/export_openapi.py
```
