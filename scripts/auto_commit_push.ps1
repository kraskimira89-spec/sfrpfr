#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Automatic git add + commit + push to origin/main.
#>
param(
  [string]$Message = "",
  [string]$Remote = "origin",
  [string]$Branch = "main",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path .git)) {
  Write-Error "Not a git repository."
}

git add -A
$status = git status --porcelain
if (-not $status) {
  Write-Host "No changes to commit."
  exit 0
}

$staged = git diff --cached --name-only
if ($staged -match '(^|/)\.env$' -or $staged -match '\.pem$' -or $staged -match 'credentials') {
  Write-Error "Suspicious files in index (.env/secrets). Commit aborted."
}

if (-not $Message) {
  $Message = "AUTO: sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

if ($DryRun) {
  Write-Host "DryRun staged files:"
  $staged
  exit 0
}

git commit -m $Message
if ($LASTEXITCODE -ne 0) {
  Write-Error "git commit failed with exit $LASTEXITCODE"
}
git push $Remote "HEAD:$Branch"
if ($LASTEXITCODE -ne 0) {
  Write-Error "git push failed with exit $LASTEXITCODE"
}
Write-Host "OK: commit + push -> $Remote/$Branch"
