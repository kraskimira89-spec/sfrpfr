# Мониторинг API (ТЗ-05) с Windows / локально.
# Пример:
#   .\scripts\ops_check.ps1
#   .\scripts\ops_check.ps1 -Url https://api.taxi-doroga-dobra.ru

param(
    [string]$Url = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = "src"

Write-Host "=== $(Get-Date -Format o) ops_check ==="
if ($Url) {
    python -m sfrfr ops-check-remote --url $Url
} else {
    python -m sfrfr ops-check-remote
}
python -m sfrfr ops-health --fail-on-alert
Write-Host "ops_check OK"
