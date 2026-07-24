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

function Get-CommitMessageFile {
  $py = Get-PythonExe
  $script = Join-Path (Get-Location) "scripts\compose_commit_message.py"
  $msgFile = Join-Path (Get-Location) ".git\AUTO_COMMIT_MSG.txt"
  $fallback = "обновить: синхронизация изменений $(Get-Date -Format 'yyyy-MM-dd HH:mm')"

  if (-not $py -or -not (Test-Path $script)) {
    [System.IO.File]::WriteAllText($msgFile, $fallback + "`n", (New-Object System.Text.UTF8Encoding $false))
    return $msgFile
  }

  $env:PYTHONIOENCODING = "utf-8"
  $env:PYTHONUTF8 = "1"
  & $py -X utf8 $script -o $msgFile | Out-Null
  if (($LASTEXITCODE -ne 0) -or -not (Test-Path $msgFile) -or -not (Get-Item $msgFile).Length) {
    [System.IO.File]::WriteAllText($msgFile, $fallback + "`n", (New-Object System.Text.UTF8Encoding $false))
  }
  return $msgFile
}

$msgFile = $null
if ($Message) {
  if ($Message -match '^\s*AUTO:\s*agent stop') {
    $msgFile = Get-CommitMessageFile
  } else {
    $msgFile = Join-Path (Get-Location) ".git\AUTO_COMMIT_MSG.txt"
    [System.IO.File]::WriteAllText($msgFile, $Message.Trim() + "`n", (New-Object System.Text.UTF8Encoding $false))
  }
} else {
  $msgFile = Get-CommitMessageFile
}

$MessagePreview = [System.IO.File]::ReadAllText($msgFile, [System.Text.Encoding]::UTF8).Trim()

if ($DryRun) {
  Write-Host "DryRun message: $MessagePreview"
  Write-Host "DryRun staged files:"
  $staged
  exit 0
}

git commit -F $msgFile
if ($LASTEXITCODE -ne 0) {
  Write-Error "git commit failed with exit $LASTEXITCODE"
}
git push $Remote "HEAD:$Branch"
if ($LASTEXITCODE -ne 0) {
  Write-Error "git push failed with exit $LASTEXITCODE"
}
Write-Host "OK: commit + push -> $Remote/$Branch"
Write-Host "message: $MessagePreview"
