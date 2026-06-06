# =============================================================================
# Forum Wedkarskie - create/refresh Kubernetes Secrets (Windows PowerShell)
#
#   .\scripts\generate-secrets.ps1            # create any missing secrets
#   .\scripts\generate-secrets.ps1 -Rotate    # force a NEW random JWT key
#
# Creates three Secrets in the forum-wedkarskie namespace:
#   - backend-secrets : SECRET_KEY (strong random hex; the audit's #1 fix)
#   - postgres-secret : dev-only DB credentials (matches the ConfigMap DSN)
#   - minio-secret    : dev-only object-store credentials
#
# postgres/minio use well-known DEV credentials on purpose so DataGrip and the
# MinIO console "just work" in class. Rotate them before any shared/graded
# deployment (see docs/12, security section).
# =============================================================================
param(
    [switch]$Rotate
)

$ErrorActionPreference = "Stop"
$NAMESPACE = "forum-wedkarskie"

Write-Host "`n=== Generating Kubernetes secrets ===" -ForegroundColor Cyan
kubectl get namespace $NAMESPACE *> $null
if ($LASTEXITCODE -ne 0) { kubectl create namespace $NAMESPACE | Out-Null }

# backend-secrets: strong random JWT signing key
$exists = $false
$ErrorActionPreference = "SilentlyContinue"
kubectl get secret backend-secrets -n $NAMESPACE -o name 2>$null | Out-Null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -eq 0) { $exists = $true }

if ($exists -and -not $Rotate) {
    Write-Host "backend-secrets already exists - keeping current SECRET_KEY (use -Rotate to change)." -ForegroundColor Gray
}
else {
    $bytes = New-Object byte[] 64
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secretKey = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    kubectl create secret generic backend-secrets `
        --namespace $NAMESPACE `
        --from-literal=SECRET_KEY=$secretKey `
        --dry-run=client -o yaml | kubectl apply -f -
    Write-Host "backend-secrets: SECRET_KEY set (128 hex chars)." -ForegroundColor Green
}

# postgres-secret (dev credentials, must match ConfigMap DATABASE_URL)
kubectl create secret generic postgres-secret `
    --namespace $NAMESPACE `
    --from-literal=POSTGRES_USER=postgres `
    --from-literal=POSTGRES_PASSWORD=postgres `
    --from-literal=POSTGRES_DB=forum_wedkarskie `
    --dry-run=client -o yaml | kubectl apply -f -
Write-Host "postgres-secret: dev credentials applied." -ForegroundColor Green

# minio-secret (dev credentials)
kubectl create secret generic minio-secret `
    --namespace $NAMESPACE `
    --from-literal=MINIO_ROOT_USER=minioadmin `
    --from-literal=MINIO_ROOT_PASSWORD=minioadmin `
    --from-literal=MINIO_ACCESS_KEY=minioadmin `
    --from-literal=MINIO_SECRET_KEY=minioadmin `
    --dry-run=client -o yaml | kubectl apply -f -
Write-Host "minio-secret: dev credentials applied." -ForegroundColor Green

Write-Host "`nDone. Secrets are in namespace '$NAMESPACE'." -ForegroundColor Cyan
