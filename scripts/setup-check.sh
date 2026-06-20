#!/usr/bin/env bash
# =============================================================================
# Forum Wedkarskie - sprawdzanie i konfiguracja Ubuntu WSL
#
#   bash setup-check.sh           # tylko sprawdzenie
#   bash setup-check.sh --install # sprawdzenie + instalacja brakujacych narzedzi
#
# Sprawdza: RAM, CPU, Docker, kubectl, minikube, helm, siec, ustawienia WSL.
# Z --install: instaluje brakujace narzedzia (minikube, kubectl, helm, uv, pnpm).
# =============================================================================

set -euo pipefail

INSTALL=false
for arg in "$@"; do
    [[ "$arg" == "--install" ]] && INSTALL=true
done

OK=0; WARN=0; FAIL=0
ACTIONS=()   # lista rzeczy ktore zostaly zainstalowane/zmienione

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; WHITE='\033[1;37m'; GRAY='\033[0;37m'; RESET='\033[0m'

pass() { echo -e "  ${GREEN}[OK]${RESET}   $1"; (( OK++ )) || true; }
warn() { echo -e "  ${YELLOW}[WARN]${RESET} $1"; (( WARN++ )) || true; }
fail() { echo -e "  ${RED}[FAIL]${RESET} $1"; (( FAIL++ )) || true; }
info() { echo -e "  ${GRAY}       $1${RESET}"; }
head() { echo -e "\n${CYAN}=== $1 ===${RESET}"; }
action() { echo -e "  ${WHITE}[EXEC]${RESET} $1"; ACTIONS+=("$1"); }

# ---------------------------------------------------------------------------
head "1. Srodowisko WSL"
# ---------------------------------------------------------------------------

if grep -qi "microsoft" /proc/version 2>/dev/null; then
    KERNEL=$(uname -r)
    pass "Uruchomiony w WSL: kernel $KERNEL"
    if echo "$KERNEL" | grep -qi "wsl2\|microsoft-standard"; then
        pass "WSL2 (wymagane dla Dockera i minikube)"
    else
        warn "Moze byc WSL1 - sprawdz: wsl --status na Windows. Minikube wymaga WSL2."
    fi
else
    warn "Nie wykryto WSL - skrypt przeznaczony dla Ubuntu WSL"
fi

# Sprawdz Ubuntu
if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    info "Dystrybucja: $PRETTY_NAME"
    if [[ "$ID" == "ubuntu" ]]; then
        pass "Ubuntu wykryte"
        if [[ "$VERSION_ID" == "22.04" || "$VERSION_ID" == "24.04" ]]; then
            pass "Wersja Ubuntu: $VERSION_ID (wspierana)"
        else
            warn "Ubuntu $VERSION_ID - zalecane 22.04 lub 24.04"
        fi
    else
        warn "Nie Ubuntu - projekt testowany na Ubuntu 22.04"
    fi
fi

# ---------------------------------------------------------------------------
head "2. Zasoby systemowe"
# ---------------------------------------------------------------------------

# RAM - obliczenia bez bc (czyste bash + awk)
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
AVAIL_RAM_KB=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(awk "BEGIN {printf \"%.1f\", $TOTAL_RAM_KB / 1024 / 1024}")
AVAIL_RAM_GB=$(awk "BEGIN {printf \"%.1f\", $AVAIL_RAM_KB / 1024 / 1024}")
# Porownania jako liczby calkowite (MB) - bez bc
TOTAL_RAM_MB=$(( TOTAL_RAM_KB / 1024 ))
AVAIL_RAM_MB=$(( AVAIL_RAM_KB / 1024 ))

info "Pamiec: dostepne ${AVAIL_RAM_GB}GB / lacznie ${TOTAL_RAM_GB}GB"

if (( TOTAL_RAM_MB >= 8192 )); then
    pass "RAM lacznie: ${TOTAL_RAM_GB}GB (wystarczajace)"
elif (( TOTAL_RAM_MB >= 6144 )); then
    warn "RAM: ${TOTAL_RAM_GB}GB - minimalne. Monitoring (Grafana/Prometheus) moze byc wolny."
    info "Zalecane: 8GB+ w .wslconfig. Bez monitoringu: minikube start --memory=4096"
else
    fail "RAM: ${TOTAL_RAM_GB}GB - za malo. Potrzeba min 6GB dla minikube (bez monitoringu)."
    info "Dodaj do C:\\Users\\<user>\\.wslconfig:"
    info "  [wsl2]"
    info "  memory=8GB"
fi

# CPU
CPU_CORES=$(nproc)
info "CPU: $CPU_CORES rdzeni dostepnych"
if (( CPU_CORES >= 4 )); then
    pass "CPU: $CPU_CORES rdzeni (wystarczajace)"
elif (( CPU_CORES >= 2 )); then
    warn "CPU: $CPU_CORES rdzenie - minikube dziala, ale wolniej. Zalecane 4+."
else
    fail "CPU: $CPU_CORES rdzen - za malo. Minikube wymaga min 2 CPU."
fi

# Dysk
DISK_AVAIL_GB=$(df -BG / | awk 'NR==2 {gsub("G",""); print $4}')
info "Dysk: dostepne ${DISK_AVAIL_GB}GB na /"
if (( DISK_AVAIL_GB >= 20 )); then
    pass "Dysk: ${DISK_AVAIL_GB}GB dostepne (wystarczajace)"
elif (( DISK_AVAIL_GB >= 10 )); then
    warn "Dysk: ${DISK_AVAIL_GB}GB - moze byc ciasno przy pelnym stacku z monitoringiem"
else
    fail "Dysk: ${DISK_AVAIL_GB}GB - za malo. Potrzeba min 10GB."
fi

# ---------------------------------------------------------------------------
head "3. Docker"
# ---------------------------------------------------------------------------

if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version 2>/dev/null)
    pass "Docker zainstalowany: $DOCKER_VER"

    # Sprawdz czy daemon dziala
    if docker info &>/dev/null; then
        pass "Docker daemon dziala"

        # Sprawdz czy mozna bez sudo
        if docker ps &>/dev/null; then
            pass "Docker dostepny bez sudo (uzytkownik w grupie docker)"
        else
            warn "Docker wymaga sudo - uruchamianie bez sudo:"
            info "  sudo usermod -aG docker \$USER && newgrp docker"
        fi

        # Sprawdz czy mamy dostep do sieci w Dockerze
        if docker run --rm --net=host busybox:stable echo "docker_net_ok" 2>/dev/null | grep -q "docker_net_ok"; then
            pass "Docker networking dziala"
        fi

    else
        warn "Docker daemon nie odpowiada"
        info "Uruchom: sudo service docker start"
        info "Lub dodaj do /etc/wsl.conf:"
        info "  [boot]"
        info "  command = service docker start"
    fi
else
    fail "Docker NIE jest zainstalowany"
    if [[ "$INSTALL" == "true" ]]; then
        action "Instalacja Docker CE..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
            sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
            sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
        sudo apt-get update -qq
        sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io
        sudo usermod -aG docker "$USER"
        sudo service docker start
        pass "Docker CE zainstalowany - wyloguj sie i zaloguj ponownie (lub: newgrp docker)"
    else
        info "Uruchom z --install aby zainstalowac automatycznie"
        info "Lub recznie: https://docs.docker.com/engine/install/ubuntu/"
    fi
fi

# ---------------------------------------------------------------------------
head "4. kubectl"
# ---------------------------------------------------------------------------

if command -v kubectl &>/dev/null; then
    KUBECTL_VER=$(kubectl version --client -o json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['clientVersion']['gitVersion'])" 2>/dev/null || kubectl version --client --short 2>/dev/null | head -1)
    pass "kubectl zainstalowany: $KUBECTL_VER"
else
    fail "kubectl NIE jest zainstalowany"
    if [[ "$INSTALL" == "true" ]]; then
        action "Instalacja kubectl..."
        KUBECTL_VERSION=$(curl -sL https://dl.k8s.io/release/stable.txt)
        curl -sLO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
        sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
        rm -f kubectl
        pass "kubectl zainstalowany: $KUBECTL_VERSION"
    else
        info "Uruchom z --install lub recznie:"
        info "  curl -LO 'https://dl.k8s.io/release/\$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl'"
        info "  sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl"
    fi
fi

# ---------------------------------------------------------------------------
head "5. minikube"
# ---------------------------------------------------------------------------

if command -v minikube &>/dev/null; then
    MINIKUBE_VER=$(minikube version --short 2>/dev/null || minikube version 2>/dev/null | head -1)
    pass "minikube zainstalowany: $MINIKUBE_VER"

    # Sprawdz status klastra
    MINIKUBE_STATUS=$(minikube status --format "{{.Host}}" 2>/dev/null || echo "Stopped")
    if [[ "$MINIKUBE_STATUS" == "Running" ]]; then
        pass "Klaster minikube: Running"
        MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "unknown")
        info "Adres IP: $MINIKUBE_IP"
        info "Dodaj do C:\\Windows\\System32\\drivers\\etc\\hosts (jako Administrator):"
        info "  $MINIKUBE_IP   forum.local"
    else
        info "Klaster minikube: $MINIKUBE_STATUS (nie uruchomiony)"
        info "Uruchom: minikube start --cpus=4 --memory=8192 --driver=docker"
    fi

    # Sprawdz driver
    DRIVER=$(minikube config get driver 2>/dev/null || echo "")
    if [[ "$DRIVER" == "docker" || -z "$DRIVER" ]]; then
        pass "Minikube driver: docker (poprawny dla WSL2)"
    else
        warn "Minikube driver: $DRIVER - zalecany 'docker' dla WSL2"
        info "Zmien: minikube config set driver docker"
    fi
else
    fail "minikube NIE jest zainstalowany"
    if [[ "$INSTALL" == "true" ]]; then
        action "Instalacja minikube..."
        curl -sLO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        sudo install minikube-linux-amd64 /usr/local/bin/minikube
        rm -f minikube-linux-amd64
        minikube config set driver docker
        pass "minikube zainstalowany"
        info "Uruchom klaster: minikube start --cpus=4 --memory=8192 --driver=docker"
    else
        info "Uruchom z --install lub recznie:"
        info "  curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64"
        info "  sudo install minikube-linux-amd64 /usr/local/bin/minikube"
        info "  minikube config set driver docker"
    fi
fi

# ---------------------------------------------------------------------------
head "6. helm"
# ---------------------------------------------------------------------------

if command -v helm &>/dev/null; then
    HELM_VER=$(helm version --short 2>/dev/null || helm version 2>/dev/null | head -1)
    pass "helm zainstalowany: $HELM_VER"
else
    fail "helm NIE jest zainstalowany"
    if [[ "$INSTALL" == "true" ]]; then
        action "Instalacja helm..."
        curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
        pass "helm zainstalowany"
    else
        info "Uruchom z --install lub recznie:"
        info "  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
    fi
fi

# ---------------------------------------------------------------------------
head "7. Python i uv (backend)"
# ---------------------------------------------------------------------------

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>/dev/null)
    info "Python: $PY_VER"
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if (( PY_MAJOR == 3 && PY_MINOR >= 12 )); then
        pass "Python 3.12+ dostepny"
    elif (( PY_MAJOR == 3 && PY_MINOR >= 10 )); then
        warn "Python $PY_VER - projekt wymaga 3.12. Mozna uzyc pyenv lub deadsnakes PPA."
        info "  sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12"
    else
        fail "Python $PY_VER - za stary. Wymagany 3.12+"
    fi
else
    fail "Python3 nie znaleziony"
fi

if command -v uv &>/dev/null; then
    UV_VER=$(uv --version 2>/dev/null)
    pass "uv (package manager): $UV_VER"
else
    warn "uv NIE jest zainstalowany (potrzebny do uruchomienia backendu lokalnie)"
    if [[ "$INSTALL" == "true" ]]; then
        action "Instalacja uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
        pass "uv zainstalowany - dodano do PATH"
        info "Uruchom ponownie terminal lub: source ~/.bashrc"
    else
        info "Instalacja: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi
fi

# ---------------------------------------------------------------------------
head "8. Node.js i pnpm (frontend)"
# ---------------------------------------------------------------------------

if command -v node &>/dev/null; then
    NODE_VER=$(node --version 2>/dev/null)
    info "Node.js: $NODE_VER"
    NODE_MAJOR=$(node --version | tr -d 'v' | cut -d. -f1)
    if (( NODE_MAJOR >= 18 )); then
        pass "Node.js $NODE_VER (wystarczajacy)"
    else
        warn "Node.js $NODE_VER - projekt zalecany na 18+. Uzyj nvm."
    fi
else
    warn "Node.js nie znaleziony (potrzebny do lokalnego dev frontendu)"
    info "Zainstaluj przez nvm: https://github.com/nvm-sh/nvm"
fi

if command -v pnpm &>/dev/null; then
    PNPM_VER=$(pnpm --version 2>/dev/null)
    pass "pnpm: $PNPM_VER"
else
    warn "pnpm NIE jest zainstalowany (potrzebny do frontendu)"
    if [[ "$INSTALL" == "true" ]] && command -v npm &>/dev/null; then
        action "Instalacja pnpm przez npm..."
        npm install -g pnpm
        pass "pnpm zainstalowany"
    else
        info "Instalacja: npm install -g pnpm  (lub: corepack enable)"
    fi
fi

# ---------------------------------------------------------------------------
head "9. Narzedzia pomocnicze"
# ---------------------------------------------------------------------------

TOOLS=("git" "curl" "jq" "make")
MISSING_TOOLS=()
for t in "${TOOLS[@]}"; do
    if command -v "$t" &>/dev/null; then
        pass "$t dostepny"
    else
        warn "$t brak"
        MISSING_TOOLS+=("$t")
    fi
done

if [[ ${#MISSING_TOOLS[@]} -gt 0 && "$INSTALL" == "true" ]]; then
    action "Instalacja brakujacych narzedzi: ${MISSING_TOOLS[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${MISSING_TOOLS[@]}"
fi

# ---------------------------------------------------------------------------
head "10. Siec WSL - sprawdzenie przekierowania portow"
# ---------------------------------------------------------------------------

# IP WSL eth0
WSL_IP=$(hostname -I | awk '{print $1}')
info "Adres IP WSL (eth0): $WSL_IP"
if [[ -n "$WSL_IP" ]]; then
    pass "WSL ma adres IP: $WSL_IP"
fi

# Sprawdz czy /etc/wsl.conf ma autostart dockera
if [[ -f /etc/wsl.conf ]]; then
    pass "/etc/wsl.conf istnieje"
    cat /etc/wsl.conf | while IFS= read -r line; do
        info "  $line"
    done
    if grep -q "command.*docker" /etc/wsl.conf 2>/dev/null; then
        pass "Docker autostart skonfigurowany w /etc/wsl.conf"
    else
        info "Brak autostaru dockera - dodaj do /etc/wsl.conf:"
        info "  [boot]"
        info "  command = service docker start"
    fi
else
    warn "/etc/wsl.conf nie istnieje"
    info "Zalecane - stworz /etc/wsl.conf:"
    info "  sudo tee /etc/wsl.conf <<EOF"
    info "  [boot]"
    info "  command = service docker start"
    info "  [network]"
    info "  generateResolvConf = true"
    info "  EOF"

    if [[ "$INSTALL" == "true" ]]; then
        action "Tworzenie /etc/wsl.conf z autostartem Dockera..."
        sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
command = service docker start

[network]
generateResolvConf = true

[interop]
enabled = true
appendWindowsPath = false
EOF
        pass "/etc/wsl.conf stworzony"
        info "Zrestartuj WSL: wsl --shutdown  (na Windows), potem uruchom Ubuntu ponownie"
    fi
fi

# Sprawdz DNS
if nslookup google.com &>/dev/null; then
    pass "DNS dziala (google.com)"
elif ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
    pass "Siec dziala (ping 8.8.8.8)"
    warn "DNS moze nie dzialac - sprawdz /etc/resolv.conf"
else
    fail "Brak polaczenia z internetem - potrzebne do pobierania obrazow Docker"
fi

# ---------------------------------------------------------------------------
head "11. Sprawdzenie projektu (opcjonalne)"
# ---------------------------------------------------------------------------

# Sprawdz czy projekt jest dostepny z WSL
WINDOWS_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n' || echo "")
PROJECT_PATHS=(
    "/mnt/d/StudiaMagisterka/Semestr2/chmury/ProjektForumWedkarskie"
    "/mnt/c/Users/${WINDOWS_USER}/Documents/ProjektForumWedkarskie"
    "$HOME/ProjektForumWedkarskie"
)

PROJECT_FOUND=""
for p in "${PROJECT_PATHS[@]}"; do
    if [[ -d "$p" && -f "$p/CLAUDE.md" ]]; then
        PROJECT_FOUND="$p"
        break
    fi
done

if [[ -n "$PROJECT_FOUND" ]]; then
    pass "Projekt znaleziony: $PROJECT_FOUND"
    info "Aby przejsc do projektu: cd '$PROJECT_FOUND'"

    # Sprawdz czy backend ma pyproject.toml
    if [[ -f "$PROJECT_FOUND/backend/pyproject.toml" ]]; then
        pass "backend/pyproject.toml istnieje"
    fi
    if [[ -f "$PROJECT_FOUND/frontend/package.json" ]]; then
        pass "frontend/package.json istnieje"
    fi
    if [[ -d "$PROJECT_FOUND/k8s" ]]; then
        pass "k8s/ manifesty dostepne"
    fi
else
    warn "Projekt nie znaleziony w typowych lokalizacjach"
    info "Projekt jest na Windows - dostepny przez /mnt/ w WSL"
    info "Np: /mnt/d/StudiaMagisterka/Semestr2/chmury/ProjektForumWedkarskie"
    info "Sprawdz: ls /mnt/d/ lub ls /mnt/c/Users/<twoj_user>/"
fi

# ---------------------------------------------------------------------------
head "12. Podsumowanie i nastepne kroki"
# ---------------------------------------------------------------------------

echo ""
echo -e "  Wyniki: ${GREEN}${OK} OK${RESET}  |  ${YELLOW}${WARN} WARN${RESET}  |  ${RED}${FAIL} FAIL${RESET}"
echo ""

if [[ ${#ACTIONS[@]} -gt 0 ]]; then
    echo -e "  ${WHITE}Wykonane akcje:${RESET}"
    for a in "${ACTIONS[@]}"; do
        echo -e "    - $a"
    done
    echo ""
fi

if (( FAIL > 0 )); then
    echo -e "  ${RED}Napraw bledy FAIL przed uruchomieniem projektu.${RESET}"
    echo -e "  Uruchom ponownie z --install aby zainstalowac brakujace narzedzia:"
    echo -e "    bash setup-check.sh --install"
elif (( WARN > 0 )); then
    echo -e "  ${YELLOW}Projekt powinien dzialac, ale przejrzyj ostrzezenia WARN.${RESET}"
else
    echo -e "  ${GREEN}Srodowisko wyglada gotowe!${RESET}"
fi

echo ""
echo -e "  ${CYAN}=== INSTRUKCJA URUCHOMIENIA PROJEKTU ===${RESET}"
echo ""
echo -e "  ${WHITE}Krok 1${RESET}: Przejdz do projektu (przez mount WSL)"
echo    "    cd /mnt/d/StudiaMagisterka/Semestr2/chmury/ProjektForumWedkarskie"
echo    "    # lub sklonuj do WSL dla lepszej wydajnosci:"
echo    "    # git clone <repo> ~/ProjektForumWedkarskie && cd ~/ProjektForumWedkarskie"
echo ""
echo -e "  ${WHITE}Krok 2${RESET}: Uruchom klaster minikube"
echo    "    minikube start --cpus=4 --memory=8192 --driver=docker"
echo    "    minikube addons enable ingress"
echo    "    minikube addons enable metrics-server"
echo ""
echo -e "  ${WHITE}Krok 3${RESET}: Zbuduj obrazy Docker w kontekscie minikube"
echo    "    eval \$(minikube docker-env)"
echo    "    docker build -t forum-wedkarskie-backend:latest backend/"
echo    "    docker build -t forum-wedkarskie-frontend:latest frontend/"
echo ""
echo -e "  ${WHITE}Krok 4${RESET}: Wygeneruj sekrety i wdróz"
echo    "    # Najpierw wygeneruj SECRET_KEY:"
echo    "    python3 -c \"import secrets; print(secrets.token_hex(32))\""
echo    "    # Zapisz w k8s/backend/secret.yaml (skopiuj secret.example.yaml)"
echo    ""
echo    "    kubectl apply -f k8s/namespace.yaml"
echo    "    kubectl apply -f k8s/postgres/"
echo    "    kubectl wait --for=condition=ready pod -l app=postgres -n forum-wedkarskie --timeout=60s"
echo    "    kubectl apply -f k8s/minio/"
echo    "    kubectl apply -f k8s/backend/"
echo    "    kubectl apply -f k8s/frontend/"
echo    "    kubectl apply -f k8s/ingress/"
echo ""
echo -e "  ${WHITE}Krok 5${RESET}: Przekieruj porty (w osobnym terminalu lub w tle)"
echo    "    kubectl port-forward svc/backend-service 8000:8000 -n forum-wedkarskie &"
echo    "    kubectl port-forward svc/frontend-service 3000:80 -n forum-wedkarskie &"
echo    "    kubectl port-forward svc/minio-service 9001:9001 -n forum-wedkarskie &"
echo ""
echo -e "  ${WHITE}Krok 6${RESET}: Dodaj hosts (w Ubuntu WSL - nie Windows):"
echo    "    MINIKUBE_IP=\$(minikube ip)"
echo    "    echo \"\$MINIKUBE_IP   forum.local\" | sudo tee -a /etc/hosts"
echo    "    # Dla Grafany:"
echo    "    echo \"\$MINIKUBE_IP   grafana.local\" | sudo tee -a /etc/hosts"
echo    "    # ORAZ na Windows (jako Administrator w PowerShell):"
echo    "    # Add-Content \$env:windir\\System32\\drivers\\etc\\hosts \"\$MINIKUBE_IP   forum.local\""
echo ""
echo -e "  ${WHITE}Krok 7 (opcjonalnie)${RESET}: Monitoring (Prometheus + Grafana + Loki)"
echo    "    # helm + skrypt install-monitoring trzeba dostosowac do bash:"
echo    "    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts"
echo    "    helm repo add grafana https://grafana.github.io/helm-charts"
echo    "    helm repo update"
echo    "    helm install monitoring prometheus-community/kube-prometheus-stack \\"
echo    "        --namespace monitoring --create-namespace \\"
echo    "        --set grafana.adminPassword=admin \\"
echo    "        --set alertmanager.enabled=false \\"
echo    "        --set grafana.resources.requests.memory=256Mi \\"
echo    "        --set grafana.resources.limits.memory=512Mi"
echo    "    kubectl port-forward svc/monitoring-grafana 3001:80 -n monitoring &"
echo ""
echo -e "  ${WHITE}Dostepne URL (po port-forward):${RESET}"
echo    "    Frontend:  http://localhost:3000"
echo    "    API Docs:  http://localhost:8000/docs"
echo    "    MinIO:     http://localhost:9001  (minioadmin / minioadmin)"
echo    "    Grafana:   http://localhost:3001  (admin / admin)"
echo ""
echo -e "  ${CYAN}Plik projektu / port-forward skrypt: scripts/portforward.ps1 (tez dziala w bash z kubectl)${RESET}"
echo ""
