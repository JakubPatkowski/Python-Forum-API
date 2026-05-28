# =============================================================================
# Forum Wędkarskie — skrypt deploymentu na minikube (Windows PowerShell)
# Uruchomienie: .\scripts\deploy.ps1
# =============================================================================

param(
    [switch]$Clean,   # -Clean: usuwa PVC postgresa i zaczyna od zera
    [switch]$Build,   # -Build: wymusza przebudowę obrazów Docker
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Użycie:
  .\scripts\deploy.ps1           # Normalny deploy (zakłada że obrazy już są)
  .\scripts\deploy.ps1 -Build    # Przebuduj obrazy i deploy
  .\scripts\deploy.ps1 -Clean    # Wyczyść bazę, przebuduj i deploy od zera
"@
    exit 0
}

$ErrorActionPreference = "Stop"
$NAMESPACE = "forum-wedkarskie"

Write-Host "`n=== Forum Wędkarskie — Deploy na minikube ===" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 1. Sprawdź czy minikube działa
# -----------------------------------------------------------------------------
Write-Host "`n[1/7] Sprawdzam minikube..." -ForegroundColor Yellow
$status = minikube status --format "{{.Host}}" 2>$null
if ($status -ne "Running") {
    Write-Host "  Uruchamiam minikube..." -ForegroundColor Gray
    minikube start
}
Write-Host "  OK — minikube działa" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 2. Ustaw kontekst Dockera na minikube (obrazy buduj w minikube, nie w Desktop)
# -----------------------------------------------------------------------------
Write-Host "`n[2/7] Ustawiam kontekst Docker na minikube..." -ForegroundColor Yellow
minikube -p minikube docker-env --shell powershell | Invoke-Expression
Write-Host "  OK" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 3. Buduj obrazy Docker (jeśli -Build lub -Clean)
# -----------------------------------------------------------------------------
if ($Build -or $Clean) {
    Write-Host "`n[3/7] Buduję obrazy Docker..." -ForegroundColor Yellow
    Write-Host "  Budowanie backend..." -ForegroundColor Gray
    docker build -t forum-wedkarskie-backend:latest backend/
    Write-Host "  Budowanie frontend..." -ForegroundColor Gray
    docker build -t forum-wedkarskie-frontend:latest frontend/
    Write-Host "  OK — obrazy zbudowane" -ForegroundColor Green
} else {
    Write-Host "`n[3/7] Pomijam budowanie obrazów (użyj -Build żeby przebudować)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 4. Namespace
# -----------------------------------------------------------------------------
Write-Host "`n[4/7] Tworzę namespace..." -ForegroundColor Yellow
kubectl apply -f k8s/namespace.yaml
Write-Host "  OK" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 5. PostgreSQL (opcjonalnie wyczyść PVC)
# -----------------------------------------------------------------------------
Write-Host "`n[5/7] Wdrażam PostgreSQL..." -ForegroundColor Yellow
if ($Clean) {
    Write-Host "  -Clean: usuwam stary PVC (czysta baza danych)..." -ForegroundColor Gray
    kubectl delete deployment postgres -n $NAMESPACE --ignore-not-found
    kubectl delete pvc postgres-pvc    -n $NAMESPACE --ignore-not-found
    Start-Sleep -Seconds 3
}
kubectl apply -f k8s/postgres/
Write-Host "  Czekam aż PostgreSQL będzie gotowy..." -ForegroundColor Gray
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=120s
Write-Host "  OK — PostgreSQL działa" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 6. Backend configmap + PVC na pliki
# -----------------------------------------------------------------------------
Write-Host "`n[6/7] Konfiguracja backendu..." -ForegroundColor Yellow
kubectl apply -f k8s/backend/configmap.yaml
kubectl apply -f k8s/backend/uploads-pvc.yaml
Write-Host "  OK" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 7. Migracja bazy danych (Alembic)
# -----------------------------------------------------------------------------
Write-Host "`n[7/7] Uruchamiam migrację bazy danych..." -ForegroundColor Yellow
kubectl delete job backend-migrate -n $NAMESPACE --ignore-not-found 2>$null
kubectl apply -f k8s/backend/migration-job.yaml

Write-Host "  Czekam na zakończenie migracji (max 3 min)..." -ForegroundColor Gray
$migrationOk = $false
for ($i = 0; $i -lt 18; $i++) {
    Start-Sleep -Seconds 10
    $logs = kubectl logs job/backend-migrate -n $NAMESPACE 2>$null
    if ($logs -match "Running upgrade 0002 -> 0003") {
        $migrationOk = $true
        break
    }
    $podStatus = kubectl get pods -n $NAMESPACE -l component=migrate --no-headers 2>$null
    if ($podStatus -match "Error.*3") {
        Write-Host "  BŁĄD migracji! Sprawdź logi:" -ForegroundColor Red
        kubectl logs job/backend-migrate -n $NAMESPACE
        exit 1
    }
    Write-Host "  ... ($([int]($i+1)*10)s)" -ForegroundColor Gray
}

if (-not $migrationOk) {
    Write-Host "  Sprawdź logi migracji:" -ForegroundColor Yellow
    kubectl logs job/backend-migrate -n $NAMESPACE
} else {
    Write-Host "  OK — wszystkie migracje przeszły" -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# 8. Backend, Frontend, pgAdmin
# -----------------------------------------------------------------------------
Write-Host "`nWdrażam aplikację..." -ForegroundColor Yellow
kubectl apply -f k8s/backend/deployment.yaml
kubectl apply -f k8s/backend/service.yaml
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/pgadmin/ 2>$null  # pgAdmin opcjonalny

Write-Host "  Czekam na backend..." -ForegroundColor Gray
kubectl rollout status deployment/backend -n $NAMESPACE --timeout=120s
Write-Host "  OK — backend działa" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Podsumowanie
# -----------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Deploy zakończony pomyślnie!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Uruchom port-forwardy (każdy w osobnym terminalu):" -ForegroundColor White
Write-Host "  kubectl port-forward svc/backend-service  8000:8000 -n $NAMESPACE" -ForegroundColor Gray
Write-Host "  kubectl port-forward svc/frontend-service 3000:80   -n $NAMESPACE" -ForegroundColor Gray
Write-Host "  kubectl port-forward svc/pgadmin-service  5050:80   -n $NAMESPACE" -ForegroundColor Gray
Write-Host ""
Write-Host "Albo użyj skryptu: .\scripts\portforward.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "Adresy:" -ForegroundColor White
Write-Host "  Swagger:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "  pgAdmin:  http://localhost:5050" -ForegroundColor Cyan
Write-Host "  K8s Dashboard: minikube dashboard" -ForegroundColor Cyan
