# =============================================================================
# Forum Wedkarskie - resetuje baze danych do zera
# Uzywaj gdy migracje sa zepsute lub chcesz czystego startu
# =============================================================================

$NAMESPACE = "forum-wedkarskie"

Write-Host "UWAGA: To usunie WSZYSTKIE dane z bazy!" -ForegroundColor Red
$confirm = Read-Host "Czy na pewno chcesz kontynuowac? (wpisz 'tak')"
if ($confirm -ne "tak") {
    Write-Host "Anulowano." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nResetowanie bazy danych..." -ForegroundColor Yellow

# Usun deployment i PVC
kubectl delete deployment postgres -n $NAMESPACE --ignore-not-found
kubectl delete pvc postgres-pvc -n $NAMESPACE --ignore-not-found
kubectl delete job backend-migrate -n $NAMESPACE --ignore-not-found

Write-Host "  Czekam az zasoby sie zwolnia (5s)..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Odtworcz postgres
kubectl apply -f k8s/postgres/
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=120s
Write-Host "  PostgreSQL gotowy (czysta baza)" -ForegroundColor Green

# Uruchom migracje
kubectl apply -f k8s/backend/migration-job.yaml
Write-Host "  Czekam na migracje..." -ForegroundColor Gray
Start-Sleep -Seconds 15
kubectl logs job/backend-migrate -n $NAMESPACE

Write-Host "`nGotowe! Zrestartuj backend:" -ForegroundColor Green
Write-Host "  kubectl rollout restart deployment/backend -n $NAMESPACE" -ForegroundColor Cyan
