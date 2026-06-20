#!/usr/bin/env bash
# =============================================================================
# Forum Wedkarskie - start everything for a demo/presentation
#
#   bash scripts/start-demo.sh           # start app + monitoring + port-forwards
#   bash scripts/start-demo.sh --build   # rebuild images first, then start
#   bash scripts/start-demo.sh --stop    # stop port-forwards + minikube
#
# What this does:
#   1. Start minikube (if not running)
#   2. Load Docker images into minikube (build with --build)
#   3. Deploy: namespace, postgres, minio, backend, frontend, ingress
#   4. Install monitoring: Prometheus + Grafana + Loki
#   5. Scale to demo-friendly replicas (1 backend, 1 frontend)
#   6. Start all port-forwards in background
#   7. Print URLs
#
# All services reachable from Windows browser at localhost.
# =============================================================================

set -euo pipefail

BUILD=false
STOP=false
for arg in "$@"; do
    case "$arg" in
        --build) BUILD=true ;;
        --stop)  STOP=true  ;;
    esac
done

NS="forum-wedkarskie"
MON_NS="monitoring"
PF_PIDFILE="/tmp/forum-portforwards.pids"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; GRAY='\033[0;37m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[demo]${RESET} $*"; }
ok()   { echo -e "  ${GREEN}[OK]${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}[!!]${RESET}  $*"; }
die()  { echo -e "  ${RED}[ERR]${RESET} $*" >&2; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}>>> $* ${RESET}"; }

# ---------------------------------------------------------------------------
# --stop
# ---------------------------------------------------------------------------
if [[ "$STOP" == "true" ]]; then
    step "Stopping port-forwards"
    if [[ -f "$PF_PIDFILE" ]]; then
        while IFS= read -r pid; do kill "$pid" 2>/dev/null || true; done < "$PF_PIDFILE"
        rm -f "$PF_PIDFILE"
        ok "Port-forwards stopped"
    else
        warn "No port-forwards running"
    fi
    step "Stopping minikube"
    minikube stop && ok "Minikube stopped - RAM freed"
    exit 0
fi

# ---------------------------------------------------------------------------
# pre-flight
# ---------------------------------------------------------------------------
cd "$REPO_ROOT"
command -v docker   &>/dev/null || die "docker not found"
command -v minikube &>/dev/null || die "minikube not found. Run: bash scripts/setup-check.sh --install"
command -v kubectl  &>/dev/null || die "kubectl not found. Run: bash scripts/setup-check.sh --install"
command -v helm     &>/dev/null || die "helm not found. Run: bash scripts/setup-check.sh --install"
docker info &>/dev/null || die "Docker daemon not running. Run: sudo service docker start"

# ---------------------------------------------------------------------------
# minikube
# ---------------------------------------------------------------------------
step "Starting minikube"
STATUS=$(minikube status --format "{{.Host}}" 2>/dev/null || echo "Stopped")
if [[ "$STATUS" != "Running" ]]; then
    # 4 CPU. UWAGA: minikube NIE pozwala zmienic CPU istniejacego klastra
    # ("You cannot change the CPUs for an existing minikube cluster") - wartosc
    # bierze sie TYLKO przy pierwszym tworzeniu klastra. Aby faktycznie zmienic
    # liczbe CPU trzeba `minikube delete` (kasuje dane!) i odtworzyc.
    # Po fixach Grafany (SQLITE_BUSY/timeouty) i Loki klaster jest stabilny pod
    # testami k6 na 4 CPU (node ~10-32%), wiec nie ma potrzeby kasowac klastra.
    log "Starting minikube with 10GB RAM, 4 CPUs..."
    minikube start --cpus=4 --memory=10240 --driver=docker
    ok "Minikube started"
else
    ok "Minikube already running ($(minikube ip))"
fi
minikube addons enable ingress        &>/dev/null
minikube addons enable metrics-server &>/dev/null
ok "Addons ready: ingress, metrics-server"

# ---------------------------------------------------------------------------
# build images (optional)
# ---------------------------------------------------------------------------
if [[ "$BUILD" == "true" ]]; then
    step "Building Docker images"
    if ! docker buildx version &>/dev/null; then
        die "docker buildx not found. Run:
  sudo rm -f /usr/local/lib/docker/cli-plugins/docker-buildx
  sudo curl -fsSL https://github.com/docker/buildx/releases/download/v0.19.3/buildx-v0.19.3.linux-amd64 -o /usr/local/lib/docker/cli-plugins/docker-buildx
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx"
    fi
    unset DOCKER_HOST DOCKER_TLS_VERIFY DOCKER_CERT_PATH MINIKUBE_ACTIVE_DOCKERD
    export DOCKER_BUILDKIT=1
    log "Building backend..."
    docker build -t forum-wedkarskie-backend:latest backend/
    log "Building frontend..."
    docker build -t forum-wedkarskie-frontend:latest frontend/
    ok "Images built"
    log "Loading images into minikube..."
    minikube image load forum-wedkarskie-backend:latest
    minikube image load forum-wedkarskie-frontend:latest
    ok "Images loaded into minikube"
fi

# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------
step "Secrets"
SECRET_FILE="k8s/backend/secret.yaml"
if [[ ! -f "$SECRET_FILE" ]]; then
    cp "k8s/backend/secret.example.yaml" "$SECRET_FILE"
    NEW_KEY=$(python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
    sed -i "s|SECRET_KEY:.*|SECRET_KEY: $NEW_KEY|" "$SECRET_FILE"
    ok "secret.yaml created with generated SECRET_KEY"
else
    ok "secret.yaml exists"
fi

# ---------------------------------------------------------------------------
# deploy app
# ---------------------------------------------------------------------------
step "Deploying application"
kubectl apply -f k8s/namespace.yaml

kubectl apply -f k8s/postgres/
log "Waiting for PostgreSQL..."
kubectl wait --for=condition=ready pod -l app=postgres -n "$NS" --timeout=90s
ok "PostgreSQL ready"

kubectl apply -f k8s/minio/ 2>/dev/null || true
kubectl wait --for=condition=ready pod -l app=minio -n "$NS" --timeout=60s 2>/dev/null && \
    ok "MinIO ready" || warn "MinIO not ready yet (may still be starting)"

kubectl apply -f k8s/backend/
log "Waiting for DB migration..."
kubectl wait --for=condition=complete job/backend-migrate -n "$NS" --timeout=120s 2>/dev/null || \
    warn "Migration job not detected (may have already run)"
log "Waiting for backend..."
kubectl rollout status deployment/backend -n "$NS" --timeout=3m
ok "Backend ready"

kubectl apply -f k8s/frontend/
kubectl rollout status deployment/frontend -n "$NS" --timeout=2m
ok "Frontend ready"

# Apply ingress (skip monitoring ingress if monitoring not yet installed)
for f in k8s/ingress/*.yaml; do
    if grep -q "namespace: monitoring" "$f" 2>/dev/null && \
       ! kubectl get namespace "$MON_NS" &>/dev/null; then
        continue
    fi
    kubectl apply -f "$f" 2>/dev/null || true
done
ok "Ingress applied"

# /etc/hosts in WSL
MINIKUBE_IP=$(minikube ip)
grep -q "forum.local" /etc/hosts 2>/dev/null || \
    echo "$MINIKUBE_IP   forum.local" | sudo tee -a /etc/hosts > /dev/null
ok "WSL /etc/hosts: forum.local -> $MINIKUBE_IP"

# ---------------------------------------------------------------------------
# scale to demo-friendly replicas
# ---------------------------------------------------------------------------
step "Setting demo replica counts (1 backend, 1 frontend)"
kubectl scale deployment backend  -n "$NS" --replicas=1
kubectl scale deployment frontend -n "$NS" --replicas=1
kubectl patch hpa backend  -n "$NS" --patch '{"spec":{"minReplicas":1,"maxReplicas":3}}' 2>/dev/null || true
kubectl patch hpa frontend -n "$NS" --patch '{"spec":{"minReplicas":1,"maxReplicas":2}}' 2>/dev/null || true
ok "Replicas: backend=1, frontend=1 (HPA will scale up under load)"

# ---------------------------------------------------------------------------
# monitoring
# ---------------------------------------------------------------------------
step "Installing monitoring (Prometheus + Grafana + Loki)"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts &>/dev/null || true
helm repo add grafana              https://grafana.github.io/helm-charts              &>/dev/null || true
helm repo update &>/dev/null

log "Installing kube-prometheus-stack (may take 5-10 min on first run)..."
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
    --namespace "$MON_NS" --create-namespace \
    -f k8s/monitoring/values-kube-prometheus-stack.yaml \
    --wait --timeout 15m --atomic=false 2>&1 | grep -v "^W\|^I\|coalesce" || true
ok "Prometheus + Grafana deployed"

log "Installing Loki + Promtail..."
helm upgrade --install loki grafana/loki-stack \
    --namespace "$MON_NS" \
    -f k8s/monitoring/values-loki-stack.yaml \
    --wait --timeout 10m --atomic=false 2>&1 | grep -v "^W\|^I\|coalesce" || true
ok "Loki deployed"

kubectl apply -f k8s/monitoring/servicemonitor-backend.yaml 2>/dev/null || true
kubectl apply -f k8s/monitoring/prometheus-rules.yaml       2>/dev/null || true
kubectl apply -f k8s/monitoring/grafana-dashboard-forum.yaml 2>/dev/null || true
kubectl apply -f k8s/monitoring/grafana-dashboard-presentation.yaml 2>/dev/null || true

# Apply monitoring ingress now that the namespace exists
kubectl apply -f k8s/ingress/ingress-monitoring.yaml 2>/dev/null || true
ok "Monitoring ingress applied"

# ---------------------------------------------------------------------------
# wait for Grafana to be ready before port-forwarding
# ---------------------------------------------------------------------------
log "Waiting for Grafana to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=grafana \
    -n "$MON_NS" --timeout=5m 2>/dev/null && \
    ok "Grafana ready" || warn "Grafana not fully ready yet (may still be starting)"

# ---------------------------------------------------------------------------
# port-forwards
# ---------------------------------------------------------------------------
step "Starting port-forwards"

# Kill any previous forwards
if [[ -f "$PF_PIDFILE" ]]; then
    while IFS= read -r pid; do kill "$pid" 2>/dev/null || true; done < "$PF_PIDFILE"
fi
: > "$PF_PIDFILE"

forward() {
    local name="$1" svc="$2" local_port="$3" remote_port="$4" ns="$5"
    if kubectl get "$svc" -n "$ns" &>/dev/null; then
        kubectl port-forward "$svc" "${local_port}:${remote_port}" \
            -n "$ns" --address 127.0.0.1 &>/dev/null &
        echo $! >> "$PF_PIDFILE"
        ok "$(printf '%-20s' "$name")  http://localhost:${local_port}"
    else
        warn "$(printf '%-20s' "$name")  not found (skipped)"
    fi
}

forward "Frontend"       "svc/frontend-service"                              3000 80   "$NS"
forward "Backend/Swagger" "svc/backend-service"                              8000 8000 "$NS"
forward "PostgreSQL"     "svc/postgres-service"                              5432 5432 "$NS"
forward "MinIO console"  "svc/minio-service"                                 9001 9001 "$NS"
# S3 API na 30900 — WYMAGANE przez upload: presigned URL-e mają w sobie
# MINIO_PUBLIC_ENDPOINT=localhost:30900, więc browser MUSI tu dosięgnąć MinIO.
# Bez tego forwardu upload/download plików z przeglądarki nie działa.
forward "MinIO S3"       "svc/minio-service"                                 30900 9000 "$NS"
forward "Grafana"        "svc/monitoring-grafana"                            3001 80   "$MON_NS"
forward "Prometheus"     "svc/monitoring-kube-prometheus-prometheus"         9090 9090 "$MON_NS"
forward "Loki"           "svc/loki"                                          3100 3100 "$MON_NS"

sleep 2  # let port-forwards bind

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}============================================${RESET}"
echo -e "${BOLD}${GREEN}  Demo ready!${RESET}"
echo -e "${BOLD}${GREEN}============================================${RESET}"
echo ""
echo -e "  ${BOLD}Open in Windows browser:${RESET}"
echo -e "    ${GREEN}http://localhost:3000${RESET}       Forum (frontend)"
echo -e "    ${GREEN}http://localhost:8000/docs${RESET}  Swagger / API"
echo -e "    ${GREEN}http://localhost:3001${RESET}       Grafana          (admin / admin)"
echo -e "    ${GREEN}http://localhost:9090${RESET}       Prometheus"
echo -e "    ${GREEN}http://localhost:9001${RESET}       MinIO console    (minioadmin / minioadmin)"
echo -e "    ${GRAY}localhost:30900${RESET}             MinIO S3         (presigned upload/download)"
echo ""
echo -e "  ${BOLD}Add to Windows hosts file${RESET} (C:\\Windows\\System32\\drivers\\etc\\hosts, as Admin):"
echo -e "    ${GRAY}$MINIKUBE_IP   forum.local   grafana.local${RESET}"
echo ""
echo -e "  ${BOLD}Useful commands:${RESET}"
echo -e "    ${GRAY}kubectl get pods -n $NS${RESET}           # app pods"
echo -e "    ${GRAY}kubectl top pods -n $NS${RESET}           # CPU/RAM per pod"
echo -e "    ${GRAY}kubectl get hpa   -n $NS${RESET}           # autoscaler status"
echo -e "    ${GRAY}bash scripts/start-demo.sh --stop${RESET}  # stop everything"
echo ""
