# Auth for Terraform/yc via SA authorized key JSON (post 2026-06-01).
# Usage: .\scripts\yc_cloud_auth.ps1 [-KeyFile path]

param(
    [string]$KeyFile = "",
    [string]$CloudId = "b1gkscu5sqpjtf5d5rbi",
    [string]$FolderId = "b1g0mhpm9tr4lrurk1bu",
    [string]$Profile = "sfrfr"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Yc = Join-Path $Root "tools\yandex-cloud\bin\yc.exe"
$DefaultKey = Join-Path $Root "secrets\yc-sa-terraform.json"
$EnvFile = Join-Path $Root "secrets\yc-cloud.env"

if (-not (Test-Path $Yc)) {
    throw "YC CLI not found: $Yc"
}

if (-not $KeyFile) {
    if (Test-Path $DefaultKey) { $KeyFile = $DefaultKey }
}

if (-not $KeyFile -or -not (Test-Path $KeyFile)) {
    Write-Host "Need SA authorized key JSON at secrets\yc-sa-terraform.json"
    Write-Host "Console: IAM -> Service accounts -> Create key -> JSON"
    Write-Host "OAuth y0_ tokens after 2026-06-01 are rejected by Cloud IAM."
    throw "SA key file missing"
}

$KeyFile = (Resolve-Path $KeyFile).Path

$plist = & $Yc config profile list 2>&1 | Out-String
if ($plist -notmatch "(?m)^\s*$Profile\b") {
    & $Yc config profile create $Profile | Out-Null
}
& $Yc config profile activate $Profile | Out-Null
& $Yc config unset token 2>$null | Out-Null
& $Yc config set service-account-key $KeyFile | Out-Null
& $Yc config set cloud-id $CloudId | Out-Null
& $Yc config set folder-id $FolderId | Out-Null

@(
    "# Yandex Cloud auth for Terraform - DO NOT COMMIT",
    "YC_SERVICE_ACCOUNT_KEY_FILE=$KeyFile",
    "YC_CLOUD_ID=$CloudId",
    "YC_FOLDER_ID=$FolderId"
) | Set-Content -Path $EnvFile -Encoding UTF8

Write-Host "Checking: resource-manager cloud list..."
& $Yc resource-manager cloud list --format text
if ($LASTEXITCODE -ne 0) {
    throw "SA key rejected by Cloud IAM (check roles / JSON key type)"
}

Write-Host "OK profile=$Profile cloud=$CloudId folder=$FolderId"
Write-Host "Next: .\scripts\tofu_plan_staging.ps1"
