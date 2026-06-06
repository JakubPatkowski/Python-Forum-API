# =============================================================================
# Forum Wedkarskie - full minikube deployment (Windows PowerShell)
#
#   .\scripts\deploy.ps1                 # deploy (assumes images already built)
#   .\scripts\deploy.ps1 -Build          # rebuild images, then deploy
#   .\scripts\deploy.ps1 -Clean          # wipe DB/MinIO volumes, rebuild, deploy
#   .\scripts\deploy.ps1 -Monitoring     # also install Prometheus/Grafana/Loki
#   .\scripts\deploy.ps1 -Lockdown       # also apply full NetworkPolicy lockdown
#   .\scripts\deploy.ps1 -Build -Monitoring
#
# This replaces the old partial script. It now covers: addons (ingress +
# metrics-server), secrets, postgres, MinIO + bucket, migrations, backend
# (+ HPA/PDB/cleanup), frontend, the safe NetworkPolicy, and the ingress.
# =============================================================================
param(
    [switch]$Build,
    [switch]$Clean,
    [switch]$Monitoring,
    [switch]$Lockdown,
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\scripts\deploy.ps1 [-Build] [-Clean] [-Monitoring] [-Lockdown]"
    exit 0
}

$ErrorActionPreference = "Stop"
$NS = "forum-wedkarskie"
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

Write-Host "`n=== Forum Wedkarskie - minikube deploy ===" -ForegroundColor Cyan

# 1. minikube up + required addons
Write-Host "`n[1/9] minikube + addons..." -ForegroundColor Yellow
$status = minikube status --format "{{.Host}}" 2>$null
if ($status -ne "Running") {
    Write-Host "  starting minikube..." -ForegroundColor Gray
    minikube start --cpus=4 --memory=6144
}
minikube addons enable ingress | Out-Null
minikube addons enable metrics-server | Out-Null
Write-Host "  OK (ingress + metrics-server enabled)" -ForegroundColor Green

# 2. Point docker at the minikube daemon
Write-Host "`n[2/9] Switching docker context to minikube..." -ForegroundColor Yellow
minikube -p minikube docker-env --shell powershell | Invoke-Expression
Write-Host "  OK" -ForegroundColor Green

# 3. Build images (only with -Build / -Clean)
if ($Build -or $Clean) {
    Write-Host "`n[3/9] Building images..." -ForegroundColor Yellow
    docker build -t forum-wedkarskie-backend:latest backend/
    docker build -t forum-wedkarskie-frontend:latest frontend/
    Write-Host "  OK" -ForegroundColor Green
}
else {
    Write-Host "`n[3/9] Skipping image build (use -Build to rebuild)" -ForegroundColor Gray
}

# 4. Namespace + secrets
Write-Host "`n[4/9] Namespace + secrets..." -ForegroundColor Yellow
kubectl apply -f k8s/namespace.yaml
& "$PSScriptRoot\generate-secrets.ps1"
Write-Host "  OK" -ForegroundColor Green

# 5. PostgreSQL (optionally wipe volume)
Write-Host "`n[5/9] PostgreSQL..." -ForegroundColor Yellow
if ($Clean) {
    Write-Host "  -Clean: deleting PVCs (postgres + minio + uploads)..." -ForegroundColor Gray
    kubectl delete deployment postgres minio backend -n $NS --ignore-not-found | Out-Null
    kubectl wait --for=delete pod -l app=postgres -n $NS --timeout=60s 2>$null
    kubectl wait --for=delete pod -l app=minio -n $NS --timeout=60s 2>$null
    kubectl wait --for=delete pod -l app=backend -n $NS --timeout=60s 2>$null
    kubectl delete pvc postgres-pvc minio-pvc backend-uploads-pvc -n $NS --ignore-not-found | Out-Null
    Start-Sleep -Seconds 3
    Start-Sleep -Seconds 3
}
kubectl apply -f k8s/postgres/
kubectl wait --for=condition=ready pod -l app=postgres -n $NS --timeout=120s
Write-Host "  OK" -ForegroundColor Green

# 6. MinIO + bucket
Write-Host "`n[6/9] MinIO + bucket..." -ForegroundColor Yellow
kubectl apply -f k8s/minio/deployment.yaml
kubectl apply -f k8s/minio/service.yaml
kubectl apply -f k8s/minio/pvc.yaml
kubectl wait --for=condition=ready pod -l app=minio -n $NS --timeout=120s
kubectl delete job minio-create-bucket -n $NS --ignore-not-found | Out-Null
kubectl apply -f k8s/minio/create-bucket-job.yaml
kubectl wait --for=condition=complete job/minio-create-bucket -n $NS --timeout=120s
Write-Host "  OK" -ForegroundColor Green

# 7. Backend config + migrations
Write-Host "`n[7/9] Backend config + DB migration..." -ForegroundColor Yellow
$ip = (minikube ip).Trim()
$rendered = Join-Path $env:TEMP "backend-config.rendered.yaml"
(Get-Content k8s/backend/configmap.yaml -Raw) -replace '<minikube-ip>', $ip | Set-Content $rendered -Encoding UTF8
kubectl apply -f $rendered
Remove-Item $rendered -ErrorAction SilentlyContinue
kubectl apply -f k8s/backend/uploads-pvc.yaml

kubectl delete job backend-migrate -n $NS --ignore-not-found | Out-Null
kubectl apply -f k8s/backend/migration-job.yaml
try {
    kubectl wait --for=condition=complete job/backend-migrate -n $NS --timeout=180s
    Write-Host "  OK - migrations applied (MinIO IP: $ip)" -ForegroundColor Green
}
catch {
    Write-Host "  Migration did not complete - logs:" -ForegroundColor Red
    kubectl logs job/backend-migrate -n $NS
    throw
}

# 8. Backend + frontend + autoscaling + NetworkPolicy + ingress
Write-Host "`n[8/9] Application workloads..." -ForegroundColor Yellow
kubectl apply -f k8s/backend/deployment.yaml
kubectl apply -f k8s/backend/service.yaml
kubectl apply -f k8s/backend/hpa.yaml
kubectl apply -f k8s/backend/pdb.yaml
kubectl apply -f k8s/backend/cleanup-cronjob.yaml
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/network-policies/postgres-allow-backend.yaml
kubectl apply -f k8s/ingress/ingress-app.yaml

if ($Lockdown) {
    Write-Host "  -Lockdown: applying full NetworkPolicy set (needs Calico CNI)..." -ForegroundColor Gray
    kubectl apply -f k8s/network-policies/full-lockdown/
}

kubectl rollout status deployment/backend -n $NS --timeout=180s
kubectl rollout status deployment/frontend -n $NS --timeout=120s
Write-Host "  OK" -ForegroundColor Green

# 9. Optional monitoring stack
if ($Monitoring) {
    Write-Host "`n[9/9] Installing monitoring stack..." -ForegroundColor Yellow
    & "$PSScriptRoot\install-monitoring.ps1"
}
else {
    Write-Host "`n[9/9] Skipping monitoring (use -Monitoring to install)" -ForegroundColor Gray
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Deploy complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nAdd this line to C:\Windows\System32\drivers\etc\hosts (as Administrator):" -ForegroundColor White
Write-Host "  $ip   forum.local" -ForegroundColor Yellow
Write-Host "`nIMPORTANT (Windows): http://forum.local works only with an active tunnel." -ForegroundColor Yellow
Write-Host "  Open a SEPARATE terminal and keep it running:" -ForegroundColor White
Write-Host "    minikube tunnel" -ForegroundColor Gray
Write-Host "  (without the tunnel use port-forward instead: .\scripts\portforward.ps1)" -ForegroundColor DarkGray
Write-Host "`nApp (after 'minikube tunnel' + hosts entry above):" -ForegroundColor White
Write-Host "  Frontend : http://forum.local" -ForegroundColor Gray
Write-Host "  Swagger  : http://forum.local/docs" -ForegroundColor Gray
Write-Host "  MinIO S3 : $ip`:30900" -ForegroundColor Gray
Write-Host "`nPanels / admin (run in separate terminals):" -ForegroundColor White
Write-Host "  .\scripts\portforward.ps1" -ForegroundColor Gray
Write-Host "  minikube dashboard" -ForegroundColor Gray
Write-Host "  .\scripts\run-load-test.ps1 -Watch" -ForegroundColor Gray
Write-Host ""
