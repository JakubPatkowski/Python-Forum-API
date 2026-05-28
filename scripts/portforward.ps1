# =============================================================================
# Forum Wędkarskie — uruchamia wszystkie port-forwardy naraz
# Ctrl+C zatrzymuje wszystkie
# =============================================================================

$NAMESPACE = "forum-wedkarskie"

Write-Host "Uruchamianie port-forwardów..." -ForegroundColor Cyan
Write-Host "Ctrl+C zatrzymuje wszystko`n" -ForegroundColor Gray

Write-Host "  Swagger/API: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Frontend:    http://localhost:3000" -ForegroundColor Green
Write-Host "  pgAdmin:     http://localhost:5050" -ForegroundColor Green
Write-Host "  Baza (raw):  localhost:5432  (user: postgres / pass: postgres / db: forum_wedkarskie)`n" -ForegroundColor Green

$jobs = @(
    Start-Job { kubectl port-forward svc/backend-service  8000:8000 -n forum-wedkarskie },
    Start-Job { kubectl port-forward svc/frontend-service 3000:80   -n forum-wedkarskie },
    Start-Job { kubectl port-forward svc/pgadmin-service  5050:80   -n forum-wedkarskie 2>$null },
    Start-Job { kubectl port-forward svc/postgres-service 5432:5432 -n forum-wedkarskie }
)

Write-Host "Port-forwardy uruchomione (PID: $($jobs.Id -join ', '))" -ForegroundColor Gray
Write-Host "Naciśnij Ctrl+C żeby zakończyć...`n" -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 5
        # Sprawdź czy jakiś job się nie wysypał
        foreach ($job in $jobs) {
            if ($job.State -eq "Failed") {
                Write-Host "Port-forward $($job.Id) padł, restartuję..." -ForegroundColor Red
            }
        }
    }
} finally {
    Write-Host "`nZatrzymuję port-forwardy..." -ForegroundColor Yellow
    $jobs | Stop-Job
    $jobs | Remove-Job
    Write-Host "Gotowe." -ForegroundColor Green
}
