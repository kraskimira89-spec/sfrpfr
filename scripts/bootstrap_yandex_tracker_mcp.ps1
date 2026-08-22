# Bootstrap Yandex Tracker MCP (greenfield, no Notion import)
# Usage: .\.venv\Scripts\Activate.ps1; .\scripts\bootstrap_yandex_tracker_mcp.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root "secrets\yandex-tracker.env"
$Example = Join-Path $Root "secrets\yandex-tracker.env.example"
$CloneDir = Join-Path $Root "tools\yandex-tracker-mcp"
$CmdLauncher = Join-Path $Root "scripts\mcp-yandex-tracker.cmd"
$VenvPip = Join-Path $Root ".venv\Scripts\pip.exe"

Write-Host "== clone aikts/yandex-tracker-mcp (if missing) =="
if (-not (Test-Path (Join-Path $CloneDir "pyproject.toml"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $CloneDir) | Out-Null
    gh repo clone aikts/yandex-tracker-mcp $CloneDir
} else {
    Write-Host "OK tools/yandex-tracker-mcp"
}

Write-Host "== pip install -e (project venv) =="
if (-not (Test-Path $VenvPip)) {
    Write-Error "Missing .venv"
}
& $VenvPip install -e $CloneDir -q

Write-Host "== secrets/yandex-tracker.env =="
if (-not (Test-Path $EnvFile)) {
    Copy-Item $Example $EnvFile
    Write-Host "Created yandex-tracker.env - set TRACKER_TOKEN and TRACKER_ORG_ID"
} else {
    Write-Host "OK yandex-tracker.env exists"
}

Write-Host ""
Write-Host "Next: fill secrets/yandex-tracker.env, add mcp.json entry:"
Write-Host $CmdLauncher
Write-Host "See docs/ops/yandex-tracker-mcp.md"
