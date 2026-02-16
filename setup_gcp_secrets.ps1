# PowerShell script to configure Google Cloud Secrets for IMSIS

$ErrorActionPreference = "Stop"

Write-Host "Configurando Google Cloud Secrets para IMSIS..."
Write-Host ""

# Check gcloud CLI
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "gcloud CLI nao encontrado. Instale em: https://cloud.google.com/sdk/docs/install"
    exit 1
}

# Set project
$projectId = "imsis-486003"
Write-Host "Verificando projeto: $projectId"
& gcloud config set project $projectId | Out-Null

# Load .env
$envPath = Join-Path (Get-Location) ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "Arquivo .env nao encontrado!"
    Write-Host "   Crie um arquivo .env com:"
    Write-Host "   DB_PASS=sua_senha_secreta"
    Write-Host "   SECRET_KEY=sua_chave_secreta"
    Write-Host "   SMTP_HOST=smtp.hostinger.com"
    Write-Host "   SMTP_PORT=465"
    Write-Host "   SMTP_USER=accounts@imsis.com.br"
    Write-Host "   SMTP_PASS=sua_senha_smtp"
    Write-Host "   SMTP_FROM=accounts@imsis.com.br"
    exit 1
}

Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) {
        return
    }
    $parts = $line.Split("=", 2)
    if ($parts.Count -ne 2) {
        return
    }
    $name = $parts[0].Trim()
    $value = $parts[1]
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
}

$required = @("DB_PASS", "SECRET_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")
$missing = @()
foreach ($key in $required) {
    $value = [Environment]::GetEnvironmentVariable($key, "Process")
    if (-not $value) {
        $missing += $key
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Variaveis ausentes no .env: $($missing -join ', ')"
    exit 1
}

function Upsert-Secret {
    param (
        [Parameter(Mandatory = $true)][string]$SecretName,
        [Parameter(Mandatory = $true)][string]$SecretValue
    )

    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & gcloud secrets describe $SecretName --quiet 2>$null | Out-Null
    $ErrorActionPreference = $prevErrorAction
    $exists = ($LASTEXITCODE -eq 0)

    if ($exists) {
        Write-Host "     $SecretName ja existe, atualizando..."
        $SecretValue | & gcloud secrets versions add $SecretName --data-file=- | Out-Null
        return
    }

    Write-Host "     Criando novo secret..."
    $SecretValue | & gcloud secrets create $SecretName --data-file=- --replication-policy=automatic --quiet | Out-Null
}

Write-Host ""
Write-Host "Criando secrets em Secret Manager..."
Write-Host ""

Write-Host "  1. Criando db-pass..."
Upsert-Secret -SecretName "db-pass" -SecretValue $env:DB_PASS

Write-Host "  2. Criando secret-key..."
Upsert-Secret -SecretName "secret-key" -SecretValue $env:SECRET_KEY

Write-Host "  3. Criando smtp-host..."
Upsert-Secret -SecretName "smtp-host" -SecretValue $env:SMTP_HOST

Write-Host "  4. Criando smtp-port..."
Upsert-Secret -SecretName "smtp-port" -SecretValue $env:SMTP_PORT

Write-Host "  5. Criando smtp-user..."
Upsert-Secret -SecretName "smtp-user" -SecretValue $env:SMTP_USER

Write-Host "  6. Criando smtp-pass..."
Upsert-Secret -SecretName "smtp-pass" -SecretValue $env:SMTP_PASS

Write-Host "  7. Criando smtp-from..."
Upsert-Secret -SecretName "smtp-from" -SecretValue $env:SMTP_FROM

Write-Host ""
Write-Host "Secrets criados com sucesso!"
Write-Host ""

Write-Host "Verificando permissoes de IAM..."
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$serviceAccount = (& gcloud run services describe imsis --region us-central1 --format='value(spec.template.spec.serviceAccountName)' 2>$null)
if (-not $serviceAccount) {
    $serviceAccount = (& gcloud iam service-accounts list --filter="displayName:Cloud Run default" --format='value(email)' 2>$null)
}
if (-not $serviceAccount) {
    $projectNumber = (& gcloud projects describe $projectId --format='value(projectNumber)' 2>$null)
    if ($projectNumber) {
        $serviceAccount = "$projectNumber-compute@developer.gserviceaccount.com"
    }
}
$ErrorActionPreference = $prevErrorAction

if (-not $serviceAccount) {
    Write-Host "Nao foi possivel identificar o service account do Cloud Run."
    Write-Host "Informe o service account e repita o script."
    exit 1
}

$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& gcloud iam service-accounts describe $serviceAccount --quiet 2>$null | Out-Null
$ErrorActionPreference = $prevErrorAction
if ($LASTEXITCODE -ne 0) {
    Write-Host "Service account nao encontrado: $serviceAccount"
    exit 1
}

Write-Host "  Service Account: $serviceAccount"
Write-Host ""
Write-Host "  Granting permissions..."

$secrets = @("db-pass", "secret-key", "smtp-host", "smtp-port", "smtp-user", "smtp-pass", "smtp-from")
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
foreach ($secret in $secrets) {
    & gcloud secrets add-iam-policy-binding $secret `
        --member="serviceAccount:$serviceAccount" `
        --role="roles/secretmanager.secretAccessor" `
        --quiet 2>$null | Out-Null
}
$ErrorActionPreference = $prevErrorAction

Write-Host ""
Write-Host "Permissoes configuradas!"
Write-Host ""
Write-Host "Proximos passos:"
Write-Host ""
Write-Host "  1. Faça commit das mudanças:"
Write-Host "     git add ."
Write-Host "     git commit -m 'feat: Configure Cloud Run with Cloud SQL and secrets'"
Write-Host ""
Write-Host "  2. Faça push para GitHub:"
Write-Host "     git push"
Write-Host ""
Write-Host "  3. Cloud Build será acionado automaticamente"
Write-Host ""
Write-Host "  4. Verifique o deploy em:"
Write-Host "     gcloud run services describe app --region us-central1 --format='value(status.url)'"
Write-Host ""
Write-Host "Done!"
