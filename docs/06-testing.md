# Testing

## Unit & integration tests

The backend test suite uses **pytest** (with `pytest-asyncio` and
`httpx.AsyncClient`). Unit tests run against an in-memory SQLite database;
integration tests use **testcontainers** to spin up a real PostgreSQL instance.

```bash
cd backend
uv run pytest                 # full suite
uv run pytest tests/unit      # unit tests only
```

Quality gates run alongside the tests:

```bash
uv run ruff check .           # lint
uv run mypy app/              # strict type checking
```

The domain, application, and presentation layers are checked under
`mypy --strict`; the transitional `app/models/` ORM layer is intentionally
exempt.

## Load testing (k6)

Load tests live in `load/k6-load-test.js` and demonstrate HPA autoscaling on
minikube. Three profiles are tuned for a 16 GB development machine:

| Profile | Shape | Purpose |
|---------|-------|---------|
| `smoke` | 1 VU / 30 s | Sanity check that the API is alive |
| `demo` | Stepped ramp 10 → 40 → 80 VU (~7 min) | Clear plateau showing HPA scaling |
| `stress` | Ramp to 150 VU (~6.5 min) | Verifies the DB connection-pool fix |

Run a profile and generate a self-contained HTML report in `load/results/`:

```bash
# Wrapper script (repo root, WSL/Linux)
bash scripts/run-load-test.sh demo

# Direct k6 invocation
k6 run -e BASE_URL=http://forum.local -e PROFILE=demo load/k6-load-test.js
```

The PowerShell wrapper also samples HPA replica counts and CPU during the run
and embeds them in the report.

### Connection-pool sizing

An early stress test exhausted the database connection pool at ~150 VUs, causing
readiness-probe failures. The pool is now configurable
(`DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=10`, `DB_POOL_TIMEOUT_SECONDS=5`) so the
budget stays within Postgres `max_connections`: 3 replicas × (10 + 10) = 60 < 100.
A short pool timeout returns a fast 5xx instead of hanging requests when the pool
is saturated.

See also: [Deployment](./04-deployment.md) · [Monitoring](./05-monitoring.md).
