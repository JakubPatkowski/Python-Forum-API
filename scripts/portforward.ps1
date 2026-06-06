# =============================================================================
# Forum Wedkarskie - start all useful port-forwards at once (Windows PowerShell)
# Ctrl+C stops them all. pgAdmin is gone (removed from k8s); use DataGrip on
# the forwarded postgres port instead.
# =============================================================================
$NS  = "forum-wedkarskie"
$MON = "monitoring"

Write-Host "Starting port-forwards (Ctrl+C to stop)`n" -ForegroundColor Cyan

# Each entry: name, namespace, "svc/<name>", "localPort:remotePort"
$targets = @(
    @{ Name = "Backend/Swagger"; NS = $NS;  Svc = "svc/backend-service";                         Ports = "8000:8000" },
    @{ Name = "Frontend";        NS = $NS;  Svc = "svc/frontend-service";                        Ports = "3000:80"   },
    @{ Name = "PostgreSQL";      NS = $NS;  Svc = "svc/postgres-service";                        Ports = "5432:5432" },
    @{ Name = "MinIO console";   NS = $NS;  Svc = "svc/minio-service";                           Ports = "9001:9001" },
    @{ Name = "Grafana";         NS = $MON; Svc = "svc/monitoring-grafana";                      Ports = "3001:80"   },
    @{ Name = "Prometheus";      NS = $MON; Svc = "svc/monitoring-kube-prometheus-prometheus";   Ports = "9090:9090" },
    # Loki zwykle odpytuje sie PRZEZ Grafane (Explore -> Loki). Ten forward jest
    # tylko dla bezposredniego dostepu do API Loki (np. http://localhost:3100/ready).
    # Sam http://localhost:3100/ w przegladarce zwraca "not found" - to NORMALNE,
    # Loki nie ma UI; uzywaj /ready lub Grafany.
    @{ Name = "Loki (API)";      NS = $MON; Svc = "svc/loki";                                    Ports = "3100:3100" }
)

$jobs = @()
foreach ($t in $targets) {
    # Only forward services that actually exist (monitoring may not be installed).
    kubectl get $t.Svc -n $t.NS *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host ("  skip {0,-16} (not found in {1})" -f $t.Name, $t.NS) -ForegroundColor DarkGray
        continue
    }
    $local = ($t.Ports -split ":")[0]
    Write-Host ("  {0,-16} -> http://localhost:{1}" -f $t.Name, $local) -ForegroundColor Green
    $jobs += Start-Job -ScriptBlock {
        param($svc, $ports, $ns)
        kubectl port-forward $svc $ports -n $ns
    } -ArgumentList $t.Svc, $t.Ports, $t.NS
}

Write-Host "`nHandy URLs:" -ForegroundColor White
Write-Host "  Swagger : http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Gray
Write-Host "  DataGrip: localhost:5432  (postgres / postgres / forum_wedkarskie)" -ForegroundColor Gray
Write-Host "  MinIO   : http://localhost:9001  (minioadmin / minioadmin)" -ForegroundColor Gray
Write-Host "  Grafana : http://localhost:3001  (admin / admin)  [needs monitoring installed]" -ForegroundColor Gray
Write-Host "  Promeths: http://localhost:9090                   [needs monitoring installed]" -ForegroundColor Gray
Write-Host "  Loki    : http://localhost:3100/ready  (API only - logi ogladaj w Grafanie)" -ForegroundColor Gray
Write-Host "`nPress Ctrl+C to stop...`n" -ForegroundColor Yellow

try {
    while ($true) { Start-Sleep -Seconds 5 }
} finally {
    Write-Host "`nStopping port-forwards..." -ForegroundColor Yellow
    $jobs | Stop-Job  -ErrorAction SilentlyContinue
    $jobs | Remove-Job -ErrorAction SilentlyContinue
    Write-Host "Done." -ForegroundColor Green
}
