# =============================================================================
# Forum Wedkarskie - diagnostyka srodowiska Windows / Docker / minikube
#
#   .\scripts\diagnose-env.ps1
#
# Sprawdza kompletnosc i poprawnosc konfiguracji:
#   - Windows: Hyper-V, WSL2, pamiEC, wirtualizacja
#   - Docker Desktop: daemon, kontekst, zasoby, wersja
#   - minikube: status, driver, kontekst kubectl, addons
#   - Siec: tunelowanie, NodePort, hosts, CORS
#   - Kubernetes: pody, PVC, secrets
#   - Metryki: Prometheus targets, cAdvisor, container_cpu series
#   - MinIO: dostepnosc S3, bucket, presigned URL flow
#
# Na koncu drukuje podsumowanie: OK / WARN / FAIL dla kazdej sekcji.
# =============================================================================
$ErrorActionPreference = "SilentlyContinue"

$NS  = "forum-wedkarskie"
$MON = "monitoring"

$results = [System.Collections.Generic.List[PSCustomObject]]::new()

function Add-Result($section, $check, $status, $detail = "") {
    $results.Add([PSCustomObject]@{
        Section = $section
        Check   = $check
        Status  = $status   # OK | WARN | FAIL
        Detail  = $detail
    })
}

function Write-Header($text) {
    Write-Host "`n$('=' * 60)" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "$('=' * 60)" -ForegroundColor Cyan
}

function Write-Check($label, $status, $detail = "") {
    $color = switch ($status) { "OK" { "Green" } "WARN" { "Yellow" } default { "Red" } }
    $icon  = switch ($status) { "OK" { "[OK  ]" } "WARN" { "[WARN]" } default { "[FAIL]" } }
    Write-Host ("  {0} {1,-42} {2}" -f $icon, $label, $detail) -ForegroundColor $color
}

# ===========================================================================
# 1. WINDOWS - wymagania systemowe
# ===========================================================================
Write-Header "1. Windows / Wirtualizacja"

# Wirtualizacja CPU
$virt = (Get-WmiObject -Class Win32_Processor -ErrorAction SilentlyContinue).VirtualizationFirmwareEnabled
if ($virt -eq $true) {
    Write-Check "CPU Virtualization (VT-x/AMD-V)" "OK" "enabled in BIOS"
    Add-Result "Windows" "CPU Virtualization" "OK"
} else {
    Write-Check "CPU Virtualization" "WARN" "could not confirm (may still work)"
    Add-Result "Windows" "CPU Virtualization" "WARN" "run msinfo32 -> Virtualization-Based Security"
}

# Hyper-V
$hv = (Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -ErrorAction SilentlyContinue).State
if ($hv -eq "Enabled") {
    Write-Check "Hyper-V" "OK" "enabled"
    Add-Result "Windows" "Hyper-V" "OK"
} else {
    Write-Check "Hyper-V" "WARN" "state: $hv (needed for Docker Desktop / minikube hyperv driver)"
    Add-Result "Windows" "Hyper-V" "WARN" "state: $hv"
}

# WSL2
$wslVersion = wsl --status 2>&1 | Select-String "Default Version"
$wslInstalled = (Get-Command wsl -ErrorAction SilentlyContinue) -ne $null
if ($wslInstalled) {
    $wslVer = wsl --list --verbose 2>&1
    Write-Check "WSL2 installed" "OK" ($wslVersion -replace "Default Version: ", "")
    Add-Result "Windows" "WSL2" "OK"
    # Sprawdz domyslna dystrybucje
    $defaultDist = $wslVer | Where-Object { $_ -match "^\*" }
    if ($defaultDist) {
        $distLine = ($defaultDist -replace "\s+", " ").Trim()
        $wsl2Check = if ($distLine -match "2$") { "OK" } else { "WARN" }
        Write-Check "WSL2 default distro" $wsl2Check $distLine
        Add-Result "Windows" "WSL2 default distro" $wsl2Check $distLine
    }
} else {
    Write-Check "WSL2 installed" "WARN" "not found - Docker Desktop may use Hyper-V backend"
    Add-Result "Windows" "WSL2" "WARN" "not installed"
}

# Pamiec RAM
$ram = [math]::Round((Get-WmiObject -Class Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$ramStatus = if ($ram -ge 16) { "OK" } elseif ($ram -ge 12) { "WARN" } else { "FAIL" }
Write-Check "RAM total" $ramStatus "${ram} GB (minikube wymaga min. 6 GB wolnych)"
Add-Result "Windows" "RAM" $ramStatus "${ram} GB"

# ===========================================================================
# 2. DOCKER DESKTOP
# ===========================================================================
Write-Header "2. Docker Desktop"

# Docker daemon
$dockerVer = docker version --format "{{.Server.Version}}" 2>&1
if ($LASTEXITCODE -eq 0 -and $dockerVer -notmatch "error") {
    Write-Check "Docker daemon running" "OK" "Server $dockerVer"
    Add-Result "Docker" "Daemon running" "OK" $dockerVer
} else {
    Write-Check "Docker daemon running" "FAIL" "docker not responding - uruchom Docker Desktop"
    Add-Result "Docker" "Daemon running" "FAIL" "not responding"
}

# Kontekst Dockera
$dockerCtx = docker context inspect --format "{{.Name}} driver={{.EndpointsValue.docker.Host}}" 2>&1
Write-Check "Docker context" "OK" $dockerCtx
Add-Result "Docker" "Context" "OK" $dockerCtx

# Docker resources (via settings - tylko info)
$dockerInfo = docker system info --format "{{.MemTotal}}" 2>&1
if ($dockerInfo -match "^\d+$") {
    $dockerMemGB = [math]::Round([long]$dockerInfo / 1GB, 1)
    $memStatus = if ($dockerMemGB -ge 6) { "OK" } else { "WARN" }
    Write-Check "Docker memory limit" $memStatus "${dockerMemGB} GB przydzielone Dockerowi"
    Add-Result "Docker" "Memory limit" $memStatus "${dockerMemGB} GB"
} else {
    Write-Check "Docker memory limit" "WARN" "nie mozna odczytac (sprawdz Docker Desktop -> Settings -> Resources)"
    Add-Result "Docker" "Memory limit" "WARN" "unreadable"
}

# Docker CPU
$dockerCPU = docker system info --format "{{.NCPU}}" 2>&1
Write-Check "Docker CPUs" "OK" "$dockerCPU vCPU dostepne"
Add-Result "Docker" "CPUs" "OK" "$dockerCPU vCPU"

# Obrazy aplikacji
foreach ($img in @("forum-wedkarskie-backend:latest", "forum-wedkarskie-frontend:latest")) {
    $imgExists = docker image inspect $img 2>&1
    if ($LASTEXITCODE -eq 0) {
        $imgDate = docker image inspect $img --format "{{.Created}}" 2>&1
        Write-Check "Image: $img" "OK" "created $imgDate"
        Add-Result "Docker" "Image $img" "OK" $imgDate
    } else {
        Write-Check "Image: $img" "FAIL" "nie istnieje - uruchom deploy.ps1 -Build"
        Add-Result "Docker" "Image $img" "FAIL" "missing"
    }
}

# ===========================================================================
# 3. MINIKUBE
# ===========================================================================
Write-Header "3. minikube"

# Status
$mkStatus = minikube status --format "Host:{{.Host}} Kubelet:{{.Kubelet}} APIServer:{{.APIServer}}" 2>&1
if ($mkStatus -match "Running") {
    Write-Check "minikube status" "OK" $mkStatus
    Add-Result "minikube" "Status" "OK" $mkStatus
} else {
    Write-Check "minikube status" "FAIL" "nie dziala: $mkStatus"
    Add-Result "minikube" "Status" "FAIL" $mkStatus
}

# Driver
$mkDriver = minikube profile list -o json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
$driverName = $mkDriver.valid[0].Config.Driver
Write-Check "minikube driver" "OK" "$driverName"
Add-Result "minikube" "Driver" "OK" $driverName

# Pamiesc przydzielona minikube — czytaj z profilu (config get memory jest pusty gdy ustawiane przez --memory)
$mkProfile = minikube profile list -o json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
$mkMem = $mkProfile.valid[0].Config.Memory
$mkCPU = $mkProfile.valid[0].Config.CPUs
$memVal = if ($mkMem -and "$mkMem" -match "^\d+$") { [int]$mkMem } else { 0 }
$memStatus = if ($memVal -ge 6000) { "OK" } elseif ($memVal -ge 4096) { "WARN" } elseif ($memVal -eq 0) { "WARN" } else { "FAIL" }
$memLabel = if ($memVal -gt 0) { "${mkMem} MB" } else { "nie mozna odczytac z profilu" }
Write-Check "minikube memory" $memStatus "$memLabel (zalecane >= 6144 dla monitoring stacku)"
Write-Check "minikube CPUs" "OK" "$mkCPU vCPU"
Add-Result "minikube" "Memory" $memStatus $memLabel
Add-Result "minikube" "CPUs" "OK" "$mkCPU vCPU"

# minikube IP
$mkIP = (minikube ip 2>&1).Trim()
if ($mkIP -match "^\d{1,3}(\.\d{1,3}){3}$") {
    Write-Check "minikube IP" "OK" $mkIP
    Add-Result "minikube" "IP" "OK" $mkIP
} else {
    Write-Check "minikube IP" "FAIL" "nie mozna uzyskac IP"
    Add-Result "minikube" "IP" "FAIL" $mkIP
    $mkIP = "192.168.49.2"  # fallback
}

# kubectl context
$kubeCtx = kubectl config current-context 2>&1
if ($kubeCtx -eq "minikube") {
    Write-Check "kubectl context" "OK" $kubeCtx
    Add-Result "minikube" "kubectl context" "OK"
} else {
    Write-Check "kubectl context" "WARN" "aktualny: $kubeCtx (oczekiwany: minikube)"
    Add-Result "minikube" "kubectl context" "WARN" "current: $kubeCtx"
}

# Addons — minikube addons list -o json zwraca tablice obiektow {Name, Status, ...}
$addonsRaw = minikube addons list -o json 2>&1
$addons = $addonsRaw | ConvertFrom-Json -ErrorAction SilentlyContinue
foreach ($addon in @("ingress", "metrics-server")) {
    # Format moze byc tablica lub slownik; obsluguj oba
    if ($addons -is [System.Collections.IEnumerable] -and $addons -isnot [string]) {
        $addonObj = $addons | Where-Object { $_.Name -eq $addon -or $_.name -eq $addon }
        $addonStatus = if ($addonObj) { if ($addonObj.Status) { $addonObj.Status } else { $addonObj.status } } else { $null }
    } else {
        $addonStatus = $null
    }
    # Fallback: zapytaj kubectl bezposrednio
    if (-not $addonStatus) {
        $nsCheck = kubectl get deployment ingress-nginx-controller -n ingress-nginx 2>&1
        if ($addon -eq "ingress") {
            $addonStatus = if ($LASTEXITCODE -eq 0) { "enabled" } else { "unknown" }
        }
        $msCheck = kubectl get deployment metrics-server -n kube-system 2>&1
        if ($addon -eq "metrics-server") {
            $addonStatus = if ($LASTEXITCODE -eq 0) { "enabled" } else { "unknown" }
        }
    }
    if ($addonStatus -eq "enabled") {
        Write-Check "Addon: $addon" "OK" "enabled"
        Add-Result "minikube" "Addon $addon" "OK"
    } elseif ($addonStatus -eq "unknown") {
        Write-Check "Addon: $addon" "WARN" "nie mozna potwierdzic statusu"
        Add-Result "minikube" "Addon $addon" "WARN" "unknown"
    } else {
        Write-Check "Addon: $addon" "FAIL" "status: $addonStatus - uruchom: minikube addons enable $addon"
        Add-Result "minikube" "Addon $addon" "FAIL" $addonStatus
    }
}

# Docker context po przełaczeniu na minikube
$mkDockerCtx = minikube docker-env --shell powershell 2>&1 | Select-String "DOCKER_HOST"
if ($mkDockerCtx) {
    Write-Check "minikube docker-env" "OK" ($mkDockerCtx -replace '.*"(.*)".*', '$1')
    Add-Result "minikube" "docker-env" "OK"
} else {
    Write-Check "minikube docker-env" "WARN" "brak DOCKER_HOST - obrazy moga nie byc widoczne w minikube"
    Add-Result "minikube" "docker-env" "WARN"
}

# ===========================================================================
# 4. KUBERNETES - pody i zasoby
# ===========================================================================
Write-Header "4. Kubernetes - pody"

# Pody aplikacji
$pods = kubectl get pods -n $NS -o json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
if ($pods -and $pods.items) {
    foreach ($pod in $pods.items) {
        $podName = $pod.metadata.name
        $phase   = $pod.status.phase
        $ready   = ($pod.status.conditions | Where-Object { $_.type -eq "Ready" }).status
        $restarts = ($pod.status.containerStatuses | Measure-Object -Property restartCount -Sum).Sum
        # Succeeded = normalny stan dla CronJob/Job podow — nie jest bledem
        $status = if ($phase -eq "Running" -and $ready -eq "True") { "OK" } elseif ($phase -eq "Succeeded") { "OK" } elseif ($phase -eq "Running") { "WARN" } else { "FAIL" }
        $restartWarn = if ($restarts -gt 5) { " [!restarts=$restarts]" } else { "" }
        Write-Check "Pod: $podName" $status "phase=$phase ready=$ready restarts=$restarts$restartWarn"
        Add-Result "Kubernetes" "Pod $podName" $status "phase=$phase restarts=$restarts"
    }
} else {
    Write-Check "Pody w $NS" "FAIL" "brak podow lub blad kubectl"
    Add-Result "Kubernetes" "Pods" "FAIL" "no pods found"
}

# PVC
$pvcs = kubectl get pvc -n $NS -o json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
if ($pvcs -and $pvcs.items) {
    foreach ($pvc in $pvcs.items) {
        $pvcName   = $pvc.metadata.name
        $pvcStatus = $pvc.status.phase
        $s = if ($pvcStatus -eq "Bound") { "OK" } else { "FAIL" }
        Write-Check "PVC: $pvcName" $s $pvcStatus
        Add-Result "Kubernetes" "PVC $pvcName" $s $pvcStatus
    }
}

# Secrets
foreach ($secret in @("backend-secrets", "minio-secret", "postgres-secret")) {
    $sec = kubectl get secret $secret -n $NS 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Check "Secret: $secret" "OK" "exists"
        Add-Result "Kubernetes" "Secret $secret" "OK"
    } else {
        Write-Check "Secret: $secret" "FAIL" "brak! Uruchom: .\scripts\generate-secrets.ps1"
        Add-Result "Kubernetes" "Secret $secret" "FAIL" "missing"
    }
}

# ===========================================================================
# 5. SIEC - tunelowanie, hosts, NodePort
# ===========================================================================
Write-Header "5. Siec / Tunelowanie"

# Sprawdz czy minikube tunnel jest aktywny (po porcie 80 na localhost)
$tunnelActive = Test-NetConnection -ComputerName 127.0.0.1 -Port 80 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($tunnelActive) {
    Write-Check "Port 80 (minikube tunnel)" "OK" "aktywny - cos nasluchuje na 127.0.0.1:80"
    Add-Result "Siec" "minikube tunnel" "OK"
} else {
    Write-Check "Port 80 (minikube tunnel)" "WARN" "brak - uruchom 'minikube tunnel' w osobnym terminalu"
    Add-Result "Siec" "minikube tunnel" "WARN" "not active"
}

# hosts file - forum.local
$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$hostsContent = Get-Content $hostsPath -ErrorAction SilentlyContinue
$forumHostEntry = $hostsContent | Where-Object { $_ -match "forum\.local" -and $_ -notmatch "^#" }
if ($forumHostEntry) {
    Write-Check "hosts: forum.local" "OK" $forumHostEntry.Trim()
    Add-Result "Siec" "hosts forum.local" "OK" $forumHostEntry.Trim()
} else {
    Write-Check "hosts: forum.local" "WARN" "brak wpisu - dodaj: $mkIP   forum.local"
    Add-Result "Siec" "hosts forum.local" "WARN" "missing - add: $mkIP   forum.local"
}

# Dostepnosc MinIO NodePort
$minioReach = Test-NetConnection -ComputerName $mkIP -Port 30900 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($minioReach) {
    Write-Check "MinIO NodePort $mkIP`:30900" "OK" "osiagalny"
    Add-Result "Siec" "MinIO NodePort" "OK"
} else {
    Write-Check "MinIO NodePort $mkIP`:30900" "WARN" "nieosiagalny - bez 'minikube tunnel' NodePort jest nieosiagalny z Windows"
    Add-Result "Siec" "MinIO NodePort" "WARN" "unreachable - need minikube tunnel"
}

# Backend health przez NodePort / ingress
$backendHealth = $null
try {
    $backendHealth = Invoke-RestMethod "http://forum.local/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Check "Backend /health via forum.local" "OK" "HTTP 200"
    Add-Result "Siec" "Backend health" "OK"
} catch {
    $code = $_.Exception.Response.StatusCode.Value__
    if ($code) {
        Write-Check "Backend /health via forum.local" "WARN" "HTTP $code (tunnel aktywny?)"
        Add-Result "Siec" "Backend health" "WARN" "HTTP $code"
    } else {
        Write-Check "Backend /health via forum.local" "WARN" "brak odpowiedzi (tunnel aktywny + hosts skonfigurowany?)"
        Add-Result "Siec" "Backend health" "WARN" "no response"
    }
}

# CORS - sprawdz konfiguracje backendu
$configmap = kubectl get configmap backend-config -n $NS -o jsonpath="{.data}" 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue
$minioEndpoint = $configmap.MINIO_PUBLIC_ENDPOINT
if ($minioEndpoint -and $minioEndpoint -ne "<minikube-ip>:30900") {
    Write-Check "MINIO_PUBLIC_ENDPOINT" "OK" $minioEndpoint
    Add-Result "Siec" "MINIO_PUBLIC_ENDPOINT" "OK" $minioEndpoint
} else {
    Write-Check "MINIO_PUBLIC_ENDPOINT" "FAIL" "wartosc: '$minioEndpoint' - wymagany deploy.ps1 z podmiana IP"
    Add-Result "Siec" "MINIO_PUBLIC_ENDPOINT" "FAIL" "not substituted"
}

# ===========================================================================
# 6. PROMETHEUS / cADVISOR - metryki
# ===========================================================================
Write-Header "6. Prometheus / cAdvisor / Metryki"

# Sprawdz port-forward na 9090
$promPort = Test-NetConnection -ComputerName 127.0.0.1 -Port 9090 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($promPort) {
    Write-Check "Prometheus port-forward :9090" "OK" "aktywny"
    Add-Result "Prometheus" "Port-forward" "OK"

    $promBase = "http://localhost:9090/api/v1"

    # Targets - kubelet/cAdvisor
    try {
        $targets = (Invoke-RestMethod "$promBase/targets" -TimeoutSec 5).data.activeTargets
        $kubeletTargets   = $targets | Where-Object { $_.labels.job -match "kubelet" }
        # cAdvisor jest scrapowany przez ten sam kubelet job (metrics_path=/metrics/cadvisor)
        $cadvisorTargets  = $targets | Where-Object { $_.labels.metrics_path -eq "/metrics/cadvisor" }
        $downTargets      = $targets | Where-Object { $_.health -eq "down" }

        $kubeletUp = $kubeletTargets | Where-Object { $_.health -eq "up" }
        $cadvisorUp = $cadvisorTargets | Where-Object { $_.health -eq "up" }

        if ($kubeletUp.Count -gt 0) {
            Write-Check "Target: kubelet" "OK" "$($kubeletUp.Count) UP z $($kubeletTargets.Count)"
            Add-Result "Prometheus" "Target kubelet" "OK"
        } else {
            Write-Check "Target: kubelet" "FAIL" "0 UP - sprawdz: Prometheus -> Status -> Targets"
            Add-Result "Prometheus" "Target kubelet" "FAIL"
        }

        if ($cadvisorUp.Count -gt 0) {
            Write-Check "Target: cAdvisor" "OK" "$($cadvisorUp.Count) UP z $($cadvisorTargets.Count)"
            Add-Result "Prometheus" "Target cAdvisor" "OK"
        } elseif ($cadvisorTargets.Count -eq 0) {
            # Brak osobnego targetu — weryfikuj przez sprawdzenie czy sa serie container_cpu
            # (na minikube cAdvisor moze byc wbudowany w kubelet bez osobnego targetu)
            Write-Check "Target: cAdvisor" "WARN" "brak osobnego targetu — weryfikowane przez serie container_cpu ponizej"
            Add-Result "Prometheus" "Target cAdvisor" "WARN" "no separate target (check container_cpu series below)"
        } else {
            $cadErr = ($cadvisorTargets | Select-Object -First 1).lastError
            Write-Check "Target: cAdvisor" "FAIL" "DOWN: $cadErr"
            Add-Result "Prometheus" "Target cAdvisor" "FAIL" $cadErr
        }

        if ($downTargets.Count -gt 0) {
            Write-Check "Targets DOWN ogolnie" "WARN" "$($downTargets.Count) targetow jest DOWN"
            Add-Result "Prometheus" "Down targets" "WARN" "$($downTargets.Count) down"
        } else {
            Write-Check "Targets DOWN ogolnie" "OK" "wszystkie UP"
            Add-Result "Prometheus" "Down targets" "OK"
        }
    } catch {
        Write-Check "Prometheus targets API" "WARN" "blad: $_"
        Add-Result "Prometheus" "Targets API" "WARN" $_
    }

    # Metryki container_cpu
    try {
        $q = [uri]::EscapeDataString("container_cpu_usage_seconds_total{namespace=`"$NS`"}")
        $cpuSeries = (Invoke-RestMethod "$promBase/query?query=$q" -TimeoutSec 5).data.result
        if ($cpuSeries.Count -gt 0) {
            # Sprawdz czy sa serie z image!='' (odfiltruj sandbox)
            $realSeries = $cpuSeries | Where-Object { $_.metric.image -ne "" -and $_.metric.image -ne $null }
            Write-Check "container_cpu series (all)" "OK" "$($cpuSeries.Count) serii (real: $($realSeries.Count))"
            Add-Result "Prometheus" "container_cpu series" "OK" "$($cpuSeries.Count) total, $($realSeries.Count) with image"
            if ($realSeries.Count -eq 0) {
                Write-Check "container_cpu (image!='')" "WARN" "wszystkie serie maja pusty label image - minikube cAdvisor ograniczenie"
                Add-Result "Prometheus" "container_cpu image label" "WARN" "empty image label"
            }
        } else {
            Write-Check "container_cpu series" "FAIL" "0 serii - cAdvisor nie scrape'uje lub metryki nie maja namespace label"
            Add-Result "Prometheus" "container_cpu series" "FAIL" "0 series"
        }
    } catch {
        Write-Check "container_cpu query" "WARN" "blad zapytania: $_"
    }

    # Metryki container_memory
    try {
        $q = [uri]::EscapeDataString("container_memory_working_set_bytes{namespace=`"$NS`"}")
        $memSeries = (Invoke-RestMethod "$promBase/query?query=$q" -TimeoutSec 5).data.result
        $memStatus = if ($memSeries.Count -gt 0) { "OK" } else { "FAIL" }
        Write-Check "container_memory series" $memStatus "$($memSeries.Count) serii"
        Add-Result "Prometheus" "container_memory series" $memStatus "$($memSeries.Count)"
    } catch {
        Write-Check "container_memory query" "WARN" "blad zapytania: $_"
    }

    # External label cluster
    try {
        $q = [uri]::EscapeDataString("kube_pod_info{namespace=`"$NS`",cluster=`"$NS`"}")
        $clusterSeries = (Invoke-RestMethod "$promBase/query?query=$q" -TimeoutSec 5).data.result
        if ($clusterSeries.Count -gt 0) {
            Write-Check "External label cluster=$NS" "OK" "$($clusterSeries.Count) serii z cluster label"
            Add-Result "Prometheus" "cluster label" "OK"
        } else {
            Write-Check "External label cluster=$NS" "WARN" "brak - helm upgrade z externalLabels nie byl wykonany lub Prometheus nie byl zrestartowany"
            Add-Result "Prometheus" "cluster label" "WARN" "missing"
        }
    } catch {
        Write-Check "cluster label query" "WARN" "blad: $_"
    }

} else {
    Write-Check "Prometheus port-forward :9090" "WARN" "nieaktywny - uruchom: .\scripts\portforward.ps1"
    Add-Result "Prometheus" "Port-forward" "WARN" "not active - run portforward.ps1"
    Write-Host "    -> Pomijam testy Prometheusa (brak polaczenia)" -ForegroundColor DarkGray
}

# ===========================================================================
# 7. MINIO - upload flow
# ===========================================================================
Write-Header "7. MinIO - upload flow"

# MinIO pod
$minioPod = kubectl get pod -n $NS -l app=minio -o jsonpath="{.items[0].metadata.name}" 2>&1
$minioPhase = kubectl get pod -n $NS -l app=minio -o jsonpath="{.items[0].status.phase}" 2>&1
if ($minioPhase -eq "Running") {
    Write-Check "MinIO pod" "OK" "$minioPod running"
    Add-Result "MinIO" "Pod" "OK"
} else {
    Write-Check "MinIO pod" "FAIL" "status: $minioPhase"
    Add-Result "MinIO" "Pod" "FAIL" $minioPhase
}

# MinIO bucket via kubectl exec
$bucketCheck = kubectl exec -n $NS $minioPod -- sh -c "mc ls local/ 2>/dev/null || ls /data/" 2>&1
if ($bucketCheck -match "forum-files") {
    Write-Check "MinIO bucket 'forum-files'" "OK" "istnieje"
    Add-Result "MinIO" "Bucket" "OK"
} else {
    Write-Check "MinIO bucket 'forum-files'" "WARN" "nie mozna potwierdzic (exec): $bucketCheck"
    Add-Result "MinIO" "Bucket" "WARN" "unverified"
}

# MinIO dostepnosc S3 API przez NodePort (wymaga aktywnego tunnel na Windows)
try {
    $minioHealth = Invoke-RestMethod "http://${mkIP}:30900/minio/health/ready" -TimeoutSec 5 -ErrorAction Stop
    Write-Check "MinIO S3 API NodePort" "OK" "healthy"
    Add-Result "MinIO" "S3 NodePort" "OK"
} catch {
    $code = $_.Exception.Response.StatusCode.Value__
    if ($code -eq 200 -or $code -eq 204) {
        Write-Check "MinIO S3 API NodePort" "OK" "HTTP $code"
        Add-Result "MinIO" "S3 NodePort" "OK"
    } else {
        Write-Check "MinIO S3 API NodePort" "WARN" "nieosiagalny (HTTP $code) - potrzebny 'minikube tunnel'"
        Add-Result "MinIO" "S3 NodePort" "WARN" "HTTP $code"
    }
}

# Sprawdz czy backend moze sie polaczyc z MinIO (przez service w klastrze)
# Uzyj python (dostepny w obrazie slim) zamiast curl (niedostepny w slim image)
$backendPod = kubectl get pod -n $NS -l app=backend -o jsonpath="{.items[0].metadata.name}" 2>&1
if ($backendPod -and $backendPod -notmatch "Error") {
    $pyScript = "import urllib.request,sys; r=urllib.request.urlopen('http://minio-service:9000/minio/health/ready',timeout=5); print(r.status)"
    $minioInCluster = kubectl exec -n $NS $backendPod -- python -c $pyScript 2>&1
    if ($minioInCluster -match "^(200|204)$") {
        Write-Check "Backend -> MinIO (in-cluster)" "OK" "HTTP $minioInCluster"
        Add-Result "MinIO" "In-cluster connectivity" "OK"
    } elseif ($minioInCluster -match "urlopen error|ConnectionRefused|timeout") {
        Write-Check "Backend -> MinIO (in-cluster)" "FAIL" "connection error: $minioInCluster"
        Add-Result "MinIO" "In-cluster connectivity" "FAIL" $minioInCluster
    } else {
        # Nieoczekiwany output — pokaz go jako WARN zamiast FAIL
        Write-Check "Backend -> MinIO (in-cluster)" "WARN" "nieoczekiwana odpowiedz: $($minioInCluster -replace '\n',' ')"
        Add-Result "MinIO" "In-cluster connectivity" "WARN" $minioInCluster
    }
}

# ===========================================================================
# PODSUMOWANIE
# ===========================================================================
Write-Header "PODSUMOWANIE"

$fails = $results | Where-Object { $_.Status -eq "FAIL" }
$warns = $results | Where-Object { $_.Status -eq "WARN" }
$oks   = $results | Where-Object { $_.Status -eq "OK" }

Write-Host "`n  Wyniki: " -NoNewline
Write-Host "$($oks.Count) OK  " -NoNewline -ForegroundColor Green
Write-Host "$($warns.Count) WARN  " -NoNewline -ForegroundColor Yellow
Write-Host "$($fails.Count) FAIL" -ForegroundColor Red

if ($fails.Count -gt 0) {
    Write-Host "`n--- FAIL (wymaga naprawy) ---" -ForegroundColor Red
    foreach ($f in $fails) {
        Write-Host ("  [{0}] {1}: {2}" -f $f.Section, $f.Check, $f.Detail) -ForegroundColor Red
    }
}

if ($warns.Count -gt 0) {
    Write-Host "`n--- WARN (warto sprawdzic) ---" -ForegroundColor Yellow
    foreach ($w in $warns) {
        Write-Host ("  [{0}] {1}: {2}" -f $w.Section, $w.Check, $w.Detail) -ForegroundColor Yellow
    }
}

Write-Host ""
if ($fails.Count -eq 0 -and $warns.Count -le 2) {
    Write-Host "  Srodowisko wyglada poprawnie." -ForegroundColor Green
} elseif ($fails.Count -eq 0) {
    Write-Host "  Brak krytycznych bledow, ale sprawdz WARNy powyzej." -ForegroundColor Yellow
} else {
    Write-Host "  Sa krytyczne problemy (FAIL) - napraw je przed uruchomieniem aplikacji." -ForegroundColor Red
}
Write-Host ""
