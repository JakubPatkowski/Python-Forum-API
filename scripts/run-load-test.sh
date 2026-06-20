#!/usr/bin/env bash
# =============================================================================
# Forum Wedkarskie - k6 load test from Ubuntu WSL + raport HTML
#
#   bash scripts/run-load-test.sh                  # profil demo (~7 min)
#   bash scripts/run-load-test.sh smoke            # 30 s sanity check
#   bash scripts/run-load-test.sh stress           # 150 VU, test granic
#   bash scripts/run-load-test.sh demo --watch     # + podpowiedz watcha
#   bash scripts/run-load-test.sh demo --no-report # bez raportu HTML
#
# W trakcie testu sampluje HPA + kubectl top (CPU/RAM podow backendu),
# po tescie generuje load/results/report-<timestamp>.html
# =============================================================================

NS="forum-wedkarskie"
PROFILE="demo"
WATCH=false
REPORT=true
for arg in "$@"; do
    case "$arg" in
        smoke|demo|stress) PROFILE="$arg" ;;
        --watch) WATCH=true ;;
        --no-report) REPORT=false ;;
    esac
done

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'

cd "$(dirname "$0")/.."

echo -e "${CYAN}=== k6 load test (profil: $PROFILE) ===${RESET}"

kubectl delete job k6-load -n "$NS" --ignore-not-found &>/dev/null

echo -e "${YELLOW}Uploading k6 script...${RESET}"
kubectl create configmap k6-script \
    --from-file=script.js=load/k6-load-test.js \
    -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

# Podmiana profilu (linia z markerem k6-profile-marker).
sed "s/value: \"demo\" # k6-profile-marker/value: \"$PROFILE\" # k6-profile-marker/" \
    load/k6-job.yaml | kubectl apply -f -

if [[ "$WATCH" == "true" ]]; then
    echo -e "${YELLOW}Tip: open another terminal and run:${RESET}"
    echo -e "  ${CYAN}watch kubectl get hpa,pods -n $NS${RESET}"
fi

echo -e "${YELLOW}Waiting for k6 pod to start...${RESET}"
kubectl wait --for=condition=ready pod -l app=k6 \
    -n "$NS" --timeout=120s 2>/dev/null || true

# --- Tail logow w tle + sampling HPA/CPU -------------------------------------
echo -e "\n${CYAN}--- k6 output (sampling HPA/CPU co 5 s) ---${RESET}\n"
kubectl logs -f job/k6-load -n "$NS" 2>/dev/null &
LOGS_PID=$!

SAMPLES_FILE="$(mktemp)"
echo -n "[" > "$SAMPLES_FILE"
FIRST=true
DEADLINE=$(( $(date +%s) + 20*60 ))

while true; do
    HPA=$(kubectl get hpa backend -n "$NS" \
        -o jsonpath='{.status.currentReplicas},{.status.desiredReplicas}' 2>/dev/null)
    CUR="${HPA%,*}"; DES="${HPA#*,}"
    [[ "$CUR" =~ ^[0-9]+$ ]] || CUR=null
    [[ "$DES" =~ ^[0-9]+$ ]] || DES=null

    CPU=null; MEM=null
    TOP=$(kubectl top pods -n "$NS" -l app.kubernetes.io/name=backend --no-headers 2>/dev/null)
    if [[ -n "$TOP" ]]; then
        CPU=$(echo "$TOP" | awk '{gsub(/[^0-9]/,"",$2); s+=$2} END {print s+0}')
        MEM=$(echo "$TOP" | awk '{gsub(/[^0-9]/,"",$3); s+=$3} END {print s+0}')
    fi

    $FIRST || echo -n "," >> "$SAMPLES_FILE"
    FIRST=false
    echo -n "{\"t\":\"$(date +%H:%M:%S)\",\"cur\":$CUR,\"des\":$DES,\"cpu\":$CPU,\"mem\":$MEM}" >> "$SAMPLES_FILE"

    SUCCEEDED=$(kubectl get job k6-load -n "$NS" -o jsonpath='{.status.succeeded}' 2>/dev/null)
    FAILED=$(kubectl get job k6-load -n "$NS" -o jsonpath='{.status.failed}' 2>/dev/null)
    [[ "$SUCCEEDED" == "1" || -n "$FAILED" ]] && break
    [[ $(date +%s) -gt $DEADLINE ]] && { echo -e "${RED}Timeout 20 min.${RESET}"; break; }
    sleep 5
done
echo -n "]" >> "$SAMPLES_FILE"

sleep 2
kill "$LOGS_PID" 2>/dev/null
wait "$LOGS_PID" 2>/dev/null

echo -e "\n${GREEN}Test finished.${RESET}"

# --- Raport HTML --------------------------------------------------------------
if [[ "$REPORT" != "true" ]]; then
    rm -f "$SAMPLES_FILE"
    exit 0
fi

echo -e "${YELLOW}Generuje raport...${RESET}"
LOGS=$(kubectl logs job/k6-load -n "$NS" 2>/dev/null)
SUMMARY=$(echo "$LOGS" | sed -n '/===K6_SUMMARY_JSON_BEGIN===/,/===K6_SUMMARY_JSON_END===/p' \
    | sed '1d;$d')

if [[ -z "$SUMMARY" ]]; then
    echo -e "${RED}Nie znaleziono podsumowania JSON w logach k6 - raport pominiety.${RESET}"
    rm -f "$SAMPLES_FILE"
    exit 1
fi

mkdir -p load/results
STAMP=$(date +%Y-%m-%d_%H-%M)
echo "$SUMMARY" > "load/results/summary-$STAMP.json"
cp "$SAMPLES_FILE" "load/results/samples-$STAMP.json"
rm -f "$SAMPLES_FILE"

SUMMARY_FILE="load/results/summary-$STAMP.json" \
SAMPLES_JSON_FILE="load/results/samples-$STAMP.json" \
OUT_FILE="load/results/report-$STAMP.html" \
python3 - <<'PYEOF'
import datetime
import os

template = open("load/report-template.html", encoding="utf-8").read()
summary = open(os.environ["SUMMARY_FILE"], encoding="utf-8").read().strip()
samples = open(os.environ["SAMPLES_JSON_FILE"], encoding="utf-8").read().strip()
html = (template
        .replace("__SUMMARY_JSON__", summary)
        .replace("__SAMPLES_JSON__", samples)
        .replace("__GENERATED_AT__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
open(os.environ["OUT_FILE"], "w", encoding="utf-8").write(html)
PYEOF

echo -e "${GREEN}Raport: load/results/report-$STAMP.html${RESET}"
echo -e "Otworz go w przegladarce (sciezka repo jest na dysku Windows, np. D:)."
