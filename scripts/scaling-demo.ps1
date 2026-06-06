# =============================================================================
# Forum Wedkarskie - autoscaling demo dashboard (Windows PowerShell)
#
#   .\scripts\scaling-demo.ps1            # live view of HPA + pods + CPU
#   .\scripts\scaling-demo.ps1 -Once      # print one snapshot and exit
#
# Run this in one terminal, then start the load test in another:
#   .\scripts\run-load-test.ps1
# Watch the backend HPA grow replicas from 2 toward 6 under load.
# =============================================================================
param(
    [switch]$Once,
    [int]$IntervalSeconds = 3
)

$NS = "forum-wedkarskie"

function Show-Snapshot {
    Clear-Host
    Write-Host "=== Forum Wedkarskie - scaling demo ===  $(Get-Date -Format HH:mm:ss)" -ForegroundColor Cyan

    Write-Host "`n-- HPA (current vs desired vs target) --" -ForegroundColor Yellow
    kubectl get hpa -n $NS

    Write-Host "`n-- Backend pods --" -ForegroundColor Yellow
    kubectl get pods -n $NS -l app.kubernetes.io/name=backend -o wide

    Write-Host "`n-- Pod resource usage (needs metrics-server) --" -ForegroundColor Yellow
    kubectl top pods -n $NS 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (metrics not ready yet - run: minikube addons enable metrics-server)" -ForegroundColor DarkGray
    }
}

if ($Once) {
    Show-Snapshot
    return
}

Write-Host "Live scaling view - press Ctrl+C to stop." -ForegroundColor Gray
try {
    while ($true) {
        Show-Snapshot
        Start-Sleep -Seconds $IntervalSeconds
    }
} finally {
    Write-Host "`nStopped." -ForegroundColor Green
}
