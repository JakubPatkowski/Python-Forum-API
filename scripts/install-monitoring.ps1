# =============================================================================
# Forum Wedkarskie - install the monitoring stack (Windows PowerShell)
#
#   .\scripts\install-monitoring.ps1
#
# Installs (via Helm, into the `monitoring` namespace):
#   - kube-prometheus-stack : Prometheus + Grafana + Alertmanager +
#                             node-exporter + kube-state-metrics
#   - loki-stack            : Loki + Promtail (logs), Grafana wired as datasource
# Then applies the app-specific ServiceMonitor, alert rules and dashboard.
#
# Prereqs: Helm 3 installed, kubectl pointing at minikube, and the app already
# deployed (scripts/deploy.ps1). metrics-server is enabled by deploy.ps1.
# =============================================================================
$ErrorActionPreference = "Stop"
$MON_NS = "monitoring"

Write-Host "`n=== Installing monitoring stack ===" -ForegroundColor Cyan

# 1) Helm repos
Write-Host "`n[1/4] Adding Helm repositories..." -ForegroundColor Yellow
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts | Out-Null
helm repo add grafana https://grafana.github.io/helm-charts | Out-Null
helm repo update | Out-Null
Write-Host "  OK" -ForegroundColor Green

# 2) kube-prometheus-stack
Write-Host "`n[2/4] Installing kube-prometheus-stack (Prometheus + Grafana)..." -ForegroundColor Yellow
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
    --namespace $MON_NS --create-namespace `
    -f k8s/monitoring/values-kube-prometheus-stack.yaml `
    --wait --timeout 10m
Write-Host "  OK" -ForegroundColor Green

# 3) loki-stack (logs)
Write-Host "`n[3/4] Installing loki-stack (Loki + Promtail)..." -ForegroundColor Yellow
helm upgrade --install loki grafana/loki-stack `
    --namespace $MON_NS --create-namespace `
    -f k8s/monitoring/values-loki-stack.yaml `
    --wait --timeout 10m
Write-Host "  OK" -ForegroundColor Green

# 4) App-specific monitoring objects
Write-Host "`n[4/5] Applying ServiceMonitor, alert rules and dashboard..." -ForegroundColor Yellow
kubectl apply -f k8s/monitoring/servicemonitor-backend.yaml
kubectl apply -f k8s/monitoring/prometheus-rules.yaml
kubectl apply -f k8s/monitoring/grafana-dashboard-forum.yaml
Write-Host "  OK" -ForegroundColor Green

# 5) Restart Grafany + kontrola OOM
# helm upgrade nie zawsze odtwarza poda Grafany, jesli zmienil sie tylko limit
# pamieci w values. rollout restart gwarantuje, ze nowy pod startuje z aktualnym
# limitem (512Mi) - bez tego stary pod moze dalej leciec na 256Mi i padac z OOM.
Write-Host "`n[5/5] Restart Grafany + kontrola OOMKilled..." -ForegroundColor Yellow
kubectl rollout restart deployment/monitoring-grafana -n $MON_NS
kubectl rollout status  deployment/monitoring-grafana -n $MON_NS --timeout=5m
Start-Sleep -Seconds 45
$gpod = kubectl get pod -n $MON_NS -l app.kubernetes.io/name=grafana -o jsonpath="{.items[0].metadata.name}"
$grestarts = kubectl get pod $gpod -n $MON_NS -o jsonpath="{.status.containerStatuses[?(@.name=='grafana')].restartCount}"
$greason = kubectl get pod $gpod -n $MON_NS -o jsonpath="{.status.containerStatuses[?(@.name=='grafana')].lastState.terminated.reason}"
if ($greason -eq "OOMKilled") {
    Write-Host "  UWAGA: Grafana nadal pada z OOMKilled - podnies grafana.resources.limits.memory (np. 640Mi) w values-kube-prometheus-stack.yaml i uruchom ponownie." -ForegroundColor Red
} elseif ([int]$grestarts -gt 1) {
    Write-Host "  Grafana restartuje sie (powod: $greason). Sprawdz: kubectl logs $gpod -n $MON_NS" -ForegroundColor Yellow
} else {
    Write-Host "  OK - Grafana stabilna (restarty: $grestarts, brak OOMKilled)." -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Monitoring installed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Grafana login: admin / admin (dev-only - change before sharing)" -ForegroundColor White
Write-Host "Open Grafana (choose one):" -ForegroundColor White
Write-Host "  kubectl port-forward svc/monitoring-grafana 3001:80 -n $MON_NS" -ForegroundColor Gray
Write-Host "  # then http://localhost:3001  ->  Dashboards -> 'Forum Overview'" -ForegroundColor Gray
Write-Host "Or apply the optional ingress and use http://grafana.local:" -ForegroundColor White
Write-Host "  kubectl apply -f k8s/ingress/ingress-monitoring.yaml" -ForegroundColor Gray
Write-Host "Check scrape target is UP: Grafana/Prometheus -> Status -> Targets ('backend')" -ForegroundColor White
Write-Host "`nVerify after ~1 min (CPU/RAM panels need the kubelet/cAdvisor target):" -ForegroundColor White
Write-Host "  kubectl top pods -n forum-wedkarskie        # kubelet metrics work" -ForegroundColor Gray
Write-Host "  kubectl get svc -n $MON_NS | findstr loki    # Loki service = 'loki'" -ForegroundColor Gray
Write-Host "  # Prometheus -> Status -> Targets : 'kubelet' and 'backend' should be UP" -ForegroundColor Gray
