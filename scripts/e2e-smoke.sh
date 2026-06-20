#!/usr/bin/env bash
# End-to-end smoke test against a running deployment.
#   usage: scripts/e2e-smoke.sh [BASE_URL]
# Exercises health probes, a public DB-backed read, and a register+login write
# path. Exits non-zero on the first failed check.
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://localhost:8000}}"
echo ">> Smoke testing ${BASE_URL}"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

echo "-- liveness"
curl -fsS "${BASE_URL}/health/live" | grep -q alive || fail "liveness probe"

echo "-- readiness (database)"
curl -fsS "${BASE_URL}/health/ready" | grep -q ready || fail "readiness probe"

echo "-- public read (GET /api/v1/categories)"
code=$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/api/v1/categories")
[ "${code}" = "200" ] || fail "GET categories returned ${code}"

echo "-- register + login (write path through the full stack)"
user="smoke_$(date +%s)"
pass="Sup3rSecret123!"
reg=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE_URL}/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${user}\",\"email\":\"${user}@example.com\",\"password\":\"${pass}\"}")
case "${reg}" in
  200|201) ;;
  *) fail "register returned ${reg}" ;;
esac

login=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE_URL}/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"login\":\"${user}\",\"password\":\"${pass}\"}")
[ "${login}" = "200" ] || fail "login returned ${login}"

echo "SMOKE OK — all checks passed"
