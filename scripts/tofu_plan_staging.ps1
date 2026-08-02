# tofu plan for SFRFR staging (no apply).
param([switch]$SavePlan)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Infra = Join-Path $Root "infra\yandex-cloud"
$Tofu = Join-Path $Root "tools\opentofu\tofu.exe"
$Yc = Join-Path $Root "tools\yandex-cloud\bin\yc.exe"
$EnvFile = Join-Path $Root "secrets\yc-cloud.env"
$DefaultKey = Join-Path $Root "secrets\yc-sa-terraform.json"
$TofuRc = Join-Path $env:APPDATA "tofu\tofu.rc"

if (-not (Test-Path $Tofu)) { throw "OpenTofu not found: $Tofu" }
if (-not (Test-Path (Join-Path $Infra "terraform.tfvars"))) {
    throw "Missing terraform.tfvars"
}

$env:PATH = "$(Split-Path $Yc -Parent);$(Split-Path $Tofu -Parent);$env:PATH"
if (Test-Path $TofuRc) { $env:TOFU_CLI_CONFIG_FILE = $TofuRc }

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*YC_SERVICE_ACCOUNT_KEY_FILE=(.+)\s*$') {
            $env:YC_SERVICE_ACCOUNT_KEY_FILE = $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
}
if (-not $env:YC_SERVICE_ACCOUNT_KEY_FILE -and (Test-Path $DefaultKey)) {
    $env:YC_SERVICE_ACCOUNT_KEY_FILE = $DefaultKey
}

if (-not $env:YC_TOKEN -and (Test-Path $Yc)) {
    $iam = & $Yc iam create-token 2>&1
    if ($LASTEXITCODE -eq 0 -and $iam) {
        $env:YC_TOKEN = ([string]$iam).Trim()
    }
}

if (-not $env:YC_TOKEN -and -not $env:YC_SERVICE_ACCOUNT_KEY_FILE) {
    throw "No auth. Run .\scripts\yc_cloud_auth.ps1 first"
}

Set-Location $Infra
Write-Host "tofu validate..."
& $Tofu validate
if ($LASTEXITCODE -ne 0) { throw "validate failed" }

Write-Host "tofu plan (no apply)..."
$planArgs = @("plan", "-input=false")
if ($SavePlan) { $planArgs += @("-out=tfplan.staging") }
& $Tofu @planArgs
exit $LASTEXITCODE
