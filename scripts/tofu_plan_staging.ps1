# tofu plan для SFRFR staging (без apply).
# Требует: yc auth (.\scripts\yc_cloud_auth.ps1) или secrets\yc-cloud.env с YC_TOKEN.

param(
    [switch]$SavePlan
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Infra = Join-Path $Root "infra\yandex-cloud"
$Tofu = Join-Path $Root "tools\opentofu\tofu.exe"
$Yc = Join-Path $Root "tools\yandex-cloud\bin\yc.exe"
$EnvFile = Join-Path $Root "secrets\yc-cloud.env"
$TofuRc = Join-Path $env:APPDATA "tofu\tofu.rc"

if (-not (Test-Path $Tofu)) {
    throw "OpenTofu не найден: $Tofu"
}
if (-not (Test-Path (Join-Path $Infra "terraform.tfvars"))) {
    throw "Нет terraform.tfvars — скопируйте из terraform.tfvars.example"
}

# PATH: yc + tofu
$env:PATH = "$(Split-Path $Yc -Parent);$(Split-Path $Tofu -Parent);$env:PATH"
if (Test-Path $TofuRc) {
    $env:TOFU_CLI_CONFIG_FILE = $TofuRc
}

# Подхватить YC_TOKEN из secrets, если есть
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*YC_TOKEN=(.+)\s*$') {
            $env:YC_TOKEN = $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

if (-not $env:YC_TOKEN) {
    # Попробовать IAM token из yc профиля
    if (Test-Path $Yc) {
        $iam = & $Yc iam create-token 2>&1
        if ($LASTEXITCODE -eq 0 -and $iam) {
            $env:YC_TOKEN = [string]$iam.Trim()
        }
    }
}

if (-not $env:YC_TOKEN) {
    throw "Нет YC_TOKEN. Сначала: .\scripts\yc_cloud_auth.ps1"
}

Set-Location $Infra
Write-Host "tofu validate..."
& $Tofu validate
if ($LASTEXITCODE -ne 0) { throw "validate failed" }

Write-Host "tofu plan (без apply)..."
$planArgs = @("plan", "-input=false")
if ($SavePlan) {
    $planArgs += @("-out=tfplan.staging")
}
& $Tofu @planArgs
exit $LASTEXITCODE
