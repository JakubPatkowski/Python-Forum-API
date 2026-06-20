#!/usr/bin/env bash
# =============================================================================
# validate-app.sh — szybka walidacja stanu Forum Wędkarskiego na minikube
# =============================================================================
# Zbiera w jednym miejscu najważniejsze sygnały zdrowia aplikacji:
#   - stan podów + RESTARTY + ostatnia przyczyna śmierci (OOMKilled / Error / exit code)
#   - zużycie CPU/RAM per pod + budżet RAM node'a (kluczowe dla OOM Grafany)
#   - status HPA, ostatnie Eventy (Warning), PVC
#   - health endpointy backendu (/, /health/live, /health/ready)
#   - sanity uploadu: czy port-forward MinIO S3 (localhost:30900) działa
#   - ogony logów: backend / minio / grafana / prometheus (z filtrem błędów)
#
# Użycie:
#   bash scripts/validate-app.sh            # pełny raport na ekran
#   bash scripts/validate-app.sh --logs     # + więcej linii logów
#   bash scripts/validate-app.sh --save      # zapis raportu do load/results/validate-*.txt
# =============================================================================
set -uo pipefail

NS="forum-wedkarskie"
MON_NS="monitoring"
LOG_LINES=20
SAVE=0
[[ "${1:-}" == "--logs" ]] && LOG_LINES=60
[[ "${1:-}" == "--save" || "${2:-}" == "--save" ]] && SAVE=1

# --- kolory (wyłączane gdy nie-terminal) -------------------------------------
if [[ -t 1 ]]; then
  R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; B=$'\e[36m'; BOLD=$'\e[1m'; X=$'\e[0m'
else
  R=""; G=""; Y=""; B=""; BOLD=""; X=""
fi

section() { echo; echo "${BOLD}${B}== $* ==${X}"; }
ok()      { echo "  ${G}OK${X}   $*"; }
warn()    { echo "  ${Y}WARN${X} $*"; }
err()     { echo "  ${R}FAIL${X} $*"; }

if ! command -v kubectl >/dev/null 2>&1; then
  echo "${R}kubectl nie znaleziony — uruchom skrypt w WSL gdzie działa minikube.${X}"
  exit 1
fi

# =============================================================================
report() {
echo "Forum Wędkarskie — raport walidacyjny   $(date '+%Y-%m-%d %H:%M:%S')"
echo "namespace=$NS  monitoring=$MON_NS"

# --- 1. PODY + RESTARTY + PRZYCZYNA ŚMIERCI ----------------------------------
section "1. Pody (status, restarty, ostatnia przyczyna)"
if ! kubectl get ns "$NS" >/dev/null 2>&1; then
  err "namespace $NS nie istnieje — czy klaster wstał? (minikube status)"
else
  kubectl get pods -n "$NS" -o wide 2>/dev/null
  echo
  # dla każdego poda: jeśli restarty > 0, pokaż ostatni terminated reason
  while read -r pod; do
    [[ -z "$pod" ]] && continue
    restarts=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)
    if [[ "${restarts:-0}" -gt 0 ]]; then
      reason=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null)
      code=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null)
      msg="$pod: ${restarts}x restart, ostatnio: ${reason:-?} (exit ${code:-?})"
      if [[ "$reason" == "OOMKilled" || "$code" == "137" ]]; then
        err "$msg  <- BRAK PAMIĘCI (podnieś limit / odchudź stack)"
      elif [[ "${restarts}" -ge 5 ]]; then
        warn "$msg  <- dużo restartów, sprawdź logi"
      else
        warn "$msg"
      fi
    fi
  done < <(kubectl get pods -n "$NS" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n')
fi

# --- 2. ZUŻYCIE ZASOBÓW + BUDŻET NODE ----------------------------------------
section "2. Zasoby CPU/RAM (per pod + node)"
echo "${BOLD}-- aplikacja ($NS) --${X}"
kubectl top pods -n "$NS" 2>/dev/null || warn "metrics-server niegotowy (kubectl top niedostępny)"
echo "${BOLD}-- monitoring ($MON_NS) --${X}"
kubectl top pods -n "$MON_NS" 2>/dev/null || warn "brak metryk dla $MON_NS"
echo "${BOLD}-- node (budżet RAM) --${X}"
kubectl top nodes 2>/dev/null || warn "brak metryk node"
echo
# ostrzeżenie o presji pamięci na node
mempress=$(kubectl get nodes -o jsonpath='{.items[*].status.conditions[?(@.type=="MemoryPressure")].status}' 2>/dev/null)
if [[ "$mempress" == *True* ]]; then
  err "node zgłasza MemoryPressure=True — to typowa przyczyna kaskady restartów (postgres/minio/grafana)"
else
  ok "node bez MemoryPressure"
fi

# --- 3. HPA + PVC ------------------------------------------------------------
section "3. HPA + PVC"
kubectl get hpa -n "$NS" 2>/dev/null || warn "brak HPA"
echo
kubectl get pvc -n "$NS" 2>/dev/null
kubectl get pvc -n "$MON_NS" 2>/dev/null

# --- 4. EVENTY (Warning) -----------------------------------------------------
section "4. Ostatnie Eventy typu Warning"
ev=$(kubectl get events -n "$NS" --field-selector type=Warning \
       --sort-by=.lastTimestamp 2>/dev/null | tail -n 15)
[[ -n "$ev" ]] && echo "$ev" || ok "brak ostrzeżeń w $NS"
evm=$(kubectl get events -n "$MON_NS" --field-selector type=Warning \
       --sort-by=.lastTimestamp 2>/dev/null | tail -n 10)
[[ -n "$evm" ]] && { echo "-- $MON_NS --"; echo "$evm"; }

# --- 5. HEALTH ENDPOINTY BACKENDU --------------------------------------------
section "5. Health backendu (in-cluster)"
bpod=$(kubectl get pod -n "$NS" -l app=backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [[ -n "$bpod" ]]; then
  for ep in / /health/live /health/ready; do
    code=$(kubectl exec -n "$NS" "$bpod" -- python -c \
      "import urllib.request,sys;
try:
 r=urllib.request.urlopen('http://localhost:8000$ep',timeout=4); print(r.status)
except Exception as e: print('ERR',e)" 2>/dev/null)
    if [[ "$code" == "200" ]]; then ok "GET $ep -> 200"
    else err "GET $ep -> ${code:-brak odpowiedzi}"; fi
  done
else
  err "pod backendu nie znaleziony"
fi

# --- 6. SANITY UPLOADU (MinIO + port-forward) --------------------------------
section "6. Upload plików / MinIO"
# 6a. czy MinIO żyje w klastrze
mpod=$(kubectl get pod -n "$NS" -l app=minio -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [[ -n "$mpod" ]]; then
  ready=$(kubectl get pod "$mpod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null)
  [[ "$ready" == "true" ]] && ok "MinIO pod Ready ($mpod)" || err "MinIO pod NIE Ready"
else
  err "pod MinIO nie znaleziony"
fi
# 6b. co backend ma w MINIO_PUBLIC_ENDPOINT (musi być osiągalne z BROWSERA = Windows)
pub=$(kubectl get configmap -n "$NS" -o jsonpath='{.items[*].data.MINIO_PUBLIC_ENDPOINT}' 2>/dev/null)
echo "  MINIO_PUBLIC_ENDPOINT = ${pub:-<niedostępne>}"
# 6c. czy port-forward S3 (localhost:30900) faktycznie odpowiada
#     to NAJCZĘSTSZA przyczyna 'upload nie działa' — presigned URL wskazuje 30900,
#     a nikt nie odpalił port-forwardu 30900->minio:9000.
pfcode=$(curl -s -o /dev/null -w "%{http_code}" --max-time 4 http://localhost:30900/minio/health/live 2>/dev/null)
if [[ "$pfcode" == "200" ]]; then
  ok "port-forward localhost:30900 -> MinIO S3 DZIAŁA (presigned URL osiągalny)"
else
  err "localhost:30900 NIE odpowiada (HTTP ${pfcode:-brak}) -> presigned upload/download padnie z przeglądarki"
  echo "       napraw: kubectl port-forward svc/minio-service 30900:9000 -n $NS --address 127.0.0.1 &"
fi
# 6d. nginx body size (413 przy dużych plikach)
fpod=$(kubectl get pod -n "$NS" -l app=frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [[ -n "$fpod" ]]; then
  bs=$(kubectl exec -n "$NS" "$fpod" -- sh -c "grep -rh client_max_body_size /etc/nginx 2>/dev/null | head -1" 2>/dev/null | tr -d ' ')
  if [[ "$bs" == *client_max_body_size* ]]; then ok "nginx $bs"
  else warn "nie znaleziono client_max_body_size w nginx -> duże pliki mogą dać 413"; fi
fi

# --- 7. LOGI (z filtrem błędów) ----------------------------------------------
section "7. Logi — ostatnie błędy"
dump_log() {
  local label="$1" sel="$2" ns="$3"
  local pod
  pod=$(kubectl get pod -n "$ns" $sel -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  echo "${BOLD}-- $label ($pod) --${X}"
  if [[ -z "$pod" ]]; then warn "pod nie znaleziony"; return; fi
  # najpierw same błędy, potem ogon
  errs=$(kubectl logs "$pod" -n "$ns" --tail=300 2>/dev/null \
         | grep -iE "error|exception|traceback|fatal|panic|oom|refused|timeout|500 |413 |denied" \
         | tail -n 12)
  if [[ -n "$errs" ]]; then echo "$errs"; else echo "  (brak wyraźnych błędów w ostatnich 300 liniach)"; fi
}
dump_log "BACKEND"    "-l app=backend"  "$NS"
dump_log "MINIO"      "-l app=minio"    "$NS"
dump_log "GRAFANA"    "-l app.kubernetes.io/name=grafana" "$MON_NS"
dump_log "PROMETHEUS" "-l app.kubernetes.io/name=prometheus" "$MON_NS"

# --- 8. SKAD IDZIE RUCH (kto odpytuje API) -----------------------------------
# Diagnoza "skoki zapytan mimo ze nikt nie korzysta": pokazuje TOP zrodlowe IP
# w logach uvicorn backendu + najczestsze sciezki. Mapowanie IP:
#   10.244.0.x = pod w klastrze (frontend/k6) | 127.0.0.1 = port-forward z Windows.
section "8. Skad idzie ruch do backendu (top IP + sciezki)"
bpods=$(kubectl get pods -n "$NS" -l app=backend -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
tmp=$(mktemp)
for bp in $bpods; do kubectl logs "$bp" -n "$NS" --tail=2000 2>/dev/null; done > "$tmp"
echo "${BOLD}-- TOP 8 zrodlowych IP (z logow uvicorn) --${X}"
grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+ - "' "$tmp" \
  | sed -E 's/:[0-9]+ - "//' | sort | uniq -c | sort -rn | head -8 \
  | sed 's/^/  /' || echo "  (brak danych)"
echo "${BOLD}-- TOP 8 sciezek --${X}"
grep -oE '"(GET|POST|PUT|DELETE|PATCH) [^ ]+' "$tmp" \
  | sort | uniq -c | sort -rn | head -8 | sed 's/^/  /' || echo "  (brak danych)"
echo "${BOLD}-- IP -> pod (do rozszyfrowania zrodla) --${X}"
kubectl get pods -n "$NS" -o jsonpath='{range .items[*]}{.status.podIP}{"\t"}{.metadata.name}{"\n"}{end}' 2>/dev/null | sed 's/^/  /'
rm -f "$tmp"

section "Podsumowanie"
echo "  Czeste przyczyny w tym projekcie:"
echo "   - Grafana/postgres restart co kilka min  -> OOM na node (sekcja 1/2: szukaj OOMKilled / exit 137)"
echo "   - Upload nie dziala                       -> brak port-forwardu localhost:30900 (sekcja 6c)"
echo "   - Duze pliki = 413                        -> nginx client_max_body_size (sekcja 6d)"
echo "   - Backend nie wraca do 1 repliki          -> HPA po pamieci (FIX: tylko CPU); sprawdz HPA sekcja 3"
echo "   - QueuePool size 5 ... w logach           -> stary obraz backendu (przebuduj: DB_POOL_SIZE nie wszedl)"
echo "   - Skoki ruchu mimo braku userow           -> sekcja 8: sprawdz top IP (frontend pod? k6? port-forward?)"
echo
echo "Koniec raportu."
}

if [[ "$SAVE" == "1" ]]; then
  mkdir -p load/results
  out="load/results/validate-$(date '+%Y%m%d-%H%M%S').txt"
  R=""; G=""; Y=""; B=""; BOLD=""; X=""
  report | tee "$out"
  echo "Zapisano: $out"
else
  report
fi
