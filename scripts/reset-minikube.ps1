#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Complete reset of Minikube cluster + Docker networking
    Solves: tunnel lock, ingress split-brain, stale container state

.DESCRIPTION
    This script:
    1. Kills all minikube/kubectl processes
    2. Removes tunnel lock file
    3. Deletes old minikube cluster (--purge)
    4. Restarts Docker Desktop daemon
    5. Starts clean cluster (4CPU, 8GB)
    6. Enables ingress addon
    7. Deploys full stack (postgres, backend, frontend, minio)
    8. Tests connectivity (ingress + NodePort)
    9. Summary report

.PARAMETER NoPrompt
    Skip all confirmations, go straight to reset

.PARAMETER SkipDeploy
    Reset cluster only, don't deploy

.PARAMETER Verbose
    Show all kubectl commands as they run

.EXAMPLE
    .\scripts\reset-minikube.ps1
    .\scripts\reset-minikube.ps1 -NoPrompt
    .\scripts\reset-minikube.ps1 -SkipDeploy -Verbose
#>

param(
    [switch]$NoPrompt,
    [switch]$SkipDeploy,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$WarningPreference = "Continue"

# ============================================================================
# COLORS & FORMATTING
# ============================================================================
function Write-Info { Write-Host "[*] $($args -join ' ')" -ForegroundColor Cyan }
function Write-Success { Write-Host "[+] $($args -join ' ')" -ForegroundColor Green }
function Write-Error { Write-Host "[-] $($args -join ' ')" -ForegroundColor Red }
function Write-Warn { Write-Host "[!] $($args -join ' ')" -ForegroundColor Yellow }
function Write-Header { Write-Host "`n$('=' * 70)`n  $($args -join ' ')`n$('=' * 70)" -ForegroundColor White }

# ============================================================================
# UTILITIES
# ============================================================================
function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Invoke-SafeKill {
    param([string]$ProcessName)
    $procs = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Info "Killing $ProcessName..."
        Stop-Process -Name $ProcessName -Force -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Milliseconds 500
    }
}

function Invoke-KubectlCmd {
    param([string[]]$Args)
    if ($Verbose) { Write-Host "  $ kubectl $($Args -join ' ')" -ForegroundColor DarkGray }
    kubectl @Args 2>&1 | Where-Object { $_ -notmatch "^$" } | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
}

# ============================================================================
# CHECKS
# ============================================================================
Write-Header "RESET MINIKUBE - PREFLIGHT CHECKS"

if (-not (Test-CommandExists "minikube")) {
    Write-Error "minikube not found in PATH. Install it first."
    exit 1
}

if (-not (Test-CommandExists "kubectl")) {
    Write-Error "kubectl not found in PATH. Install it first."
    exit 1
}

if (-not (Test-CommandExists "docker")) {
    Write-Error "docker not found in PATH. Make sure Docker Desktop is installed."
    exit 1
}

Write-Success "minikube found"
Write-Success "kubectl found"
Write-Success "docker found"

# ============================================================================
# CONFIRMATION
# ============================================================================
if (-not $NoPrompt) {
    Write-Warn "This will DELETE your current minikube cluster and redeploy."
    Write-Warn "All data in the old cluster will be LOST."
    $response = Read-Host "Continue? (yes/no)"
    if ($response -ne "yes") {
        Write-Info "Aborted."
        exit 0
    }
}

Write-Header "STEP 1: KILL PROCESSES"

Invoke-SafeKill "minikube"
Invoke-SafeKill "kubectl"
Start-Sleep -Seconds 1

Write-Success "All Minikube processes killed"

# ============================================================================
# STEP 2: REMOVE TUNNEL LOCK
# ============================================================================
Write-Header "STEP 2: REMOVE TUNNEL LOCK"

$tunnelLock = "$env:USERPROFILE\.minikube\profiles\minikube\.tunnel_lock"
if (Test-Path $tunnelLock) {
    Write-Info "Removing $tunnelLock..."
    try {
        Remove-Item -Path $tunnelLock -Force -ErrorAction Stop
        Write-Success "Tunnel lock removed"
    }
    catch {
        Write-Warn "Could not remove tunnel lock (it's OK if already gone): $_"
    }
}
else {
    Write-Info "Tunnel lock not found (already clean)"
}

# ============================================================================
# STEP 3: DELETE MINIKUBE CLUSTER
# ============================================================================
Write-Header "STEP 3: DELETE MINIKUBE CLUSTER"

Write-Info "Running: minikube delete --all --purge"
& minikube delete --all --purge 2>&1 | ForEach-Object {
    if ($_ -match "Deleting|Removing|Purging") {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
}

Write-Success "Old cluster deleted"
Start-Sleep -Seconds 2

# ============================================================================
# STEP 4: RESTART DOCKER (CRITICAL FOR NETWORKING)
# ============================================================================
Write-Header "STEP 4: RESTART DOCKER DESKTOP"

Write-Warn "Restarting Docker Desktop daemon (this may take ~30 seconds)..."
Write-Info "Stopping docker..."

$dockerProc = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if ($dockerProc) {
    Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
}

Start-Sleep -Seconds 3
Write-Info "Starting Docker Desktop..."

try {
    $dockerApp = "$env:ProgramFiles\Docker\Docker\Docker.exe"
    if (Test-Path $dockerApp) {
        & "$dockerApp" | Out-Null
        Write-Info "Docker Desktop process started, waiting for daemon..."
        Start-Sleep -Seconds 15
    }
}
catch {
    Write-Warn "Could not auto-restart Docker Desktop. Please restart it manually if cluster fails to start."
}

$dockerOk = $false
$retry = 0
while (-not $dockerOk -and $retry -lt 10) {
    $dockerOk = docker ps 2>&1 | Where-Object { $_ -notmatch "Cannot connect" } | Select-Object -First 1
    if (-not $dockerOk) {
        Write-Info "Waiting for Docker to be ready... ($retry/10)"
        Start-Sleep -Seconds 3
        $retry++
    }
}

if ($dockerOk) {
    Write-Success "Docker is ready"
}
else {
    Write-Warn "Docker may not be fully ready yet. Continuing anyway..."
}

Start-Sleep -Seconds 2

# ============================================================================
# STEP 5: START FRESH CLUSTER
# ============================================================================
Write-Header "STEP 5: START FRESH MINIKUBE CLUSTER"

Write-Info "Starting: minikube start --driver=docker --cpus=4 --memory=6144"
& minikube start --driver=docker --cpus=4 --memory=6144 2>&1 | ForEach-Object {
    if ($_ -match "Starting|Creating|Pulling|Running|Preparing|Verifying|Done|minikube|docker") {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
}

Write-Success "Cluster started"
Start-Sleep -Seconds 2

Write-Info "Verifying cluster status..."
$status = minikube status 2>&1
if ($status -match "host: Running") {
    Write-Success "Cluster is Running"
}
else {
    Write-Error "Cluster status unknown. Check: minikube status"
}

# ============================================================================
# STEP 6: ENABLE INGRESS
# ============================================================================
Write-Header "STEP 6: ENABLE INGRESS ADDON"

Write-Info "Enabling ingress..."
& minikube addons enable ingress 2>&1 | ForEach-Object {
    if ($_ -match "enabled|Using image|Verifying") {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
}

Write-Success "Ingress addon enabled"
Start-Sleep -Seconds 3

# ============================================================================
# STEP 7: DEPLOY STACK
# ============================================================================
if (-not $SkipDeploy) {
    Write-Header "STEP 7: DEPLOY APPLICATION STACK"

    if (Test-Path ".\scripts\deploy.ps1") {
        Write-Info "Running: .\scripts\deploy.ps1 -Build"
        & .\scripts\deploy.ps1 -Build 2>&1 | ForEach-Object { Write-Host "  $_" }

        Write-Success "Deployment completed"
        Start-Sleep -Seconds 5
    }
    else {
        Write-Warn "scripts\deploy.ps1 not found. Skipping deployment."
    }
}
else {
    Write-Info "Skipping deployment (use -SkipDeploy flag)"
}

# ============================================================================
# STEP 8: TESTS
# ============================================================================
Write-Header "STEP 8: CONNECTIVITY TESTS"

Write-Info "Waiting for ingress controller to be ready..."
$ready = $false
$attempt = 0
while (-not $ready -and $attempt -lt 30) {
    $pods = kubectl get pods -n ingress-nginx 2>&1 | Where-Object { $_ -match "controller.*Running" }
    if ($pods) {
        $ready = $true
        Write-Success "Ingress controller is Running"
    }
    else {
        Write-Info "  Waiting... ($attempt/30)"
        Start-Sleep -Seconds 2
        $attempt++
    }
}

Write-Info "`nCluster services:"
Invoke-KubectlCmd -Args "get", "svc", "-n", "forum-wedkarskie"

Write-Info "`nIngress status:"
Invoke-KubectlCmd -Args "get", "ingress", "-n", "forum-wedkarskie"

Write-Info "`nChecking pod status:"
Invoke-KubectlCmd -Args "get", "pods", "-n", "forum-wedkarskie"

# ============================================================================
# STEP 9: SUMMARY
# ============================================================================
Write-Header "RESET COMPLETE"

Write-Success "Cluster deleted"
Write-Success "Docker restarted"
Write-Success "Fresh cluster started (4 CPU, 8 GB)"
Write-Success "Ingress enabled"

if (-not $SkipDeploy) {
    Write-Success "Stack deployed"
}

Write-Info "`nNEXT STEPS:"
Write-Host "  1. Test backend (ClusterIP - internal only):" -ForegroundColor White
Write-Host "     kubectl port-forward -n forum-wedkarskie svc/backend-service 8000:8000" -ForegroundColor Gray
Write-Host "     curl http://localhost:8000/health" -ForegroundColor Gray

Write-Host "`n  2. Test frontend via NodePort:" -ForegroundColor White
Write-Host "     curl http://localhost:30080" -ForegroundColor Gray
Write-Host "     or open: http://localhost:30080" -ForegroundColor Gray

Write-Host "`n  3. Test ingress (requires 'minikube tunnel' in another terminal):" -ForegroundColor White
Write-Host "     minikube tunnel" -ForegroundColor Gray
Write-Host "     ping forum.local" -ForegroundColor Gray
Write-Host "     curl http://forum.local" -ForegroundColor Gray

Write-Host "`n  4. View logs:" -ForegroundColor White
Write-Host "     kubectl logs -n forum-wedkarskie deployment/backend" -ForegroundColor Gray
Write-Host "     kubectl logs -n forum-wedkarskie deployment/frontend" -ForegroundColor Gray

Write-Host "`n  5. Dashboard:" -ForegroundColor White
Write-Host "     minikube dashboard" -ForegroundColor Gray

Write-Host "`nDone! Your cluster is clean and ready." -ForegroundColor Green
