# =============================================================================
# Forum Wedkarskie - run the k6 load test in-cluster (Windows PowerShell)
#
#   .\scripts\run-load-test.ps1            # run and stream k6 output
#   .\scripts\run-load-test.ps1 -Watch     # also open HPA + pod watches
#
# It (re)creates the k6-script ConfigMap from load/k6-load-test.js, launches
# the Job, and tails its logs. Run scripts\scaling-demo.ps1 in another terminal
# (or pass -Watch) to see the HPA add replicas while the test runs.
# =============================================================================
param(
    [switch]$Watch
)

$ErrorActionPreference = "Stop"
$NAMESPACE = "forum-wedkarskie"

Write-Host "`n=== k6 load test ===" -ForegroundColor Cyan

# Fresh Job each run.
kubectl delete job k6-load -n $NAMESPACE --ignore-not-found | Out-Null

# Script -> ConfigMap (single source of truth: load/k6-load-test.js).
Write-Host "Uploading load/k6-load-test.js as ConfigMap 'k6-script'..." -ForegroundColor Yellow
kubectl create configmap k6-script `
    --from-file=script.js=load/k6-load-test.js `
    -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f load/k6-job.yaml

if ($Watch) {
    Write-Host "Opening HPA + pod watches in new windows..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl get hpa backend -n $NAMESPACE -w"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=backend -w"
}

Write-Host "Waiting for the k6 pod to start..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=k6 -n $NAMESPACE --timeout=60s 2>$null

Write-Host "`n--- k6 output (Ctrl+C to stop tailing; the Job keeps running) ---`n" -ForegroundColor Cyan
kubectl logs -f job/k6-load -n $NAMESPACE

Write-Host "`nTip: watch scaling with  .\scripts\scaling-demo.ps1" -ForegroundColor Gray
