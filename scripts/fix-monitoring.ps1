# =============================================================================
# Forum Wedkarskie - apply the monitoring stability fixes and verify them.
#
#   .\scripts\fix-monitoring.ps1
#
# Co robi (po kolei):
#   1. Upgrade kube-prometheus-stack z nowymi limitami (Grafana 512Mi -> koniec
#      z OOMKilled, Alertmanager wylaczony, Prometheus odchudzony).
#   2. Upgrade loki-stack z mniejszym footprintem.
#   3. Wymusza restart Grafany (zeby od razu wziela nowe limity).
#   4. Czeka az Grafana bedzie Ready i SPRAWDZA, czy nie restartuje sie z OOM.
#   5. Wypisuje zuzycie pamieci wezla i status podow monitoringu.
#
# Prereq: minikube dziala, kubectl + helm w PATH, aplikacja wdrozona (deploy.ps1).
# =============================================================================
$ErrorActionPreference = "Stop"
$MON = "monitoring"

Write-Host "`n=== Naprawa i stabilizacja monitoringu ===" -ForegroundColor Cyan

# --- 1. Prometheus + Grafana --------------------------------------------------
Write-Host "`n[1/5] helm upgrade: kube-prometheus-stack (nowe limity)..." -ForegroundColor Yellow
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
    --namespace $MON --create-namespace `
    -f k8s/monitoring/values-kube-prometheus-stack.yaml `
    --wait --timeout 10m
Write-Host "  OK" -ForegroundColor Green

# --- 2. Loki ------------------------------------------------------------------
Write-Host "`n[2/5] helm upgrade: loki-stack (odchudzony)..." -ForegroundColor Yellow
helm upgrade --install loki grafana/loki-stack `
    --namespace $MON --create-namespace `
    -f k8s/monitoring/values-loki-stack.yaml `
    --wait --timeout 10m
Write-Host "  OK" -ForegroundColor Green

# --- 3. Wymus swiezy pod Grafany ----------------------------------------------
# helm upgrade nie zawsze restartuje poda, jesli zmienil sie tylko limit przez
# values; rollout restart gwarantuje, ze nowy pod startuje z 512Mi.
Write-Host "`n[3/5] Restart Grafany (zeby wziela nowy limit 512Mi)..." -ForegroundColor Yellow
kubectl rollout restart deployment/monitoring-grafana -n $MON
kubectl rollout status  deployment/monitoring-grafana -n $MON --timeout=5m
Write-Host "  OK" -ForegroundColor Green

# --- 4. Sprawdz, czy Grafana NIE restartuje sie z OOM -------------------------
Write-Host "`n[4/5] Kontrola stabilnosci Grafany (60 s obserwacji)..." -ForegroundColor Yellow
Start-Sleep -Seconds 60
$pod = kubectl get pod -n $MON -l app.kubernetes.io/name=grafana -o jsonpath="{.items[0].metadata.name}"
$restarts = kubectl get pod $pod -n $MON -o jsonpath="{.status.containerStatuses[?(@.name=='grafana')].restartCount}"
$lastReason = kubectl get pod $pod -n $MON -o jsonpath="{.status.containerStatuses[?(@.name=='grafana')].lastState.terminated.reason}"
Write-Host ("  Pod: {0}" -f $pod) -ForegroundColor Gray
Write-Host ("  Restarty kontenera grafana: {0}" -f $restarts) -ForegroundColor Gray
if ($lastReason -eq "OOMKilled") {
    Write-Host "  UWAGA: ostatni restart to OOMKilled - limit nadal za niski!" -ForegroundColor Red
    Write-Host "  Podnies grafana.resources.limits.memory w values-kube-prometheus-stack.yaml (np. 640Mi) i uruchom skrypt ponownie." -ForegroundColor Red
} elseif ([int]$restarts -gt 1) {
    Write-Host "  Grafana wciaz sie restartuje (powod: $lastReason). Sprawdz logi: kubectl logs $pod -n $MON" -ForegroundColor Yellow
} else {
    Write-Host "  OK - Grafana stabilna, brak OOMKilled." -ForegroundColor Green
}

# --- 5. Podsumowanie zasobow --------------------------------------------------
Write-Host "`n[5/5] Stan zasobow:" -ForegroundColor Yellow
Write-Host "--- Wezel (RAM/CPU) ---" -ForegroundColor Gray
kubectl top nodes
Write-Host "--- Pody monitoringu ---" -ForegroundColor Gray
kubectl get pods -n $MON -o wide
Write-Host "--- Zuzycie pamieci podow monitoringu ---" -ForegroundColor Gray
kubectl top pods -n $MON 2>$null

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Gotowe." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Dostep do paneli (osobny terminal):" -ForegroundColor White
Write-Host "  .\scripts\portforward.ps1" -ForegroundColor Gray
Write-Host "  -> Grafana:    http://localhost:3001   (admin / admin)" -ForegroundColor Gray
Write-Host "  -> Prometheus: http://localhost:9090" -ForegroundColor Gray
Write-Host "Logi (Loki) ogladaj w Grafanie: Explore -> zrodlo 'Loki' ->" -ForegroundColor White
Write-Host "  {namespace=`"forum-wedkarskie`", app=`"backend`"}" -ForegroundColor Gray
Write-Host "Uwaga: http://localhost:3100 w przegladarce zwraca 'not found' - to NORMALNE." -ForegroundColor DarkGray
Write-Host "       Loki nie ma wlasnego UI; sprawdzenie zywotnosci: http://localhost:3100/ready" -ForegroundColor DarkGray
