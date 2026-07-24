#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Automatic git add + commit + push to origin/main.
  Сообщение коммита: явно через -Message, иначе ИИ/эвристика на русском
  (scripts/compose_commit_message.py).
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

function Get-PythonExe {
  $venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $cmd = Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
}

function Get-CommitMessageRu {
  $py = Get-PythonExe
  $script = Join-Path (Get-Location) "scripts\compose_commit_message.py"
  if (-not $py -or -not (Test-Path $script)) {
    return "обновить: синхронизация изменений $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
  }
  try {
    $generated = & $py $script 2>$null
    if ($LASTEXITCODE -eq 0 -and $generated) {
      $text = ($generated | Out-String).Trim()
      if ($text) { return $text }
    }
  } catch {}
  return "обновить: синхронизация изменений $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

if (-not $Message) {
  $Message = Get-CommitMessageRu
}

# Не оставляем старый английский шаблон
if ($Message -match '^\s*AUTO:\s*agent stop') {
  $Message = Get-CommitMessageRu
}

if ($DryRun) {
  Write-Host "DryRun message: $Message"
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
Write-Host "message: $Message"
