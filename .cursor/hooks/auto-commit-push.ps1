#!/usr/bin/env pwsh
# Cursor stop-hook: автокоммит и пуш после завершения агента.
# Сообщение коммита формирует scripts/compose_commit_message.py (ИИ на русском / эвристика).
# Читает JSON со stdin, пишет JSON-ответ в stdout.
$ErrorActionPreference = "Continue"
try {
  $null = [Console]::In.ReadToEnd()
} catch {}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$out = @{ continue = $true }
try {
  # Без -Message: скрипт сам соберёт русское описание по diff
  $log = & "$repoRoot\scripts\auto_commit_push.ps1" 2>&1
  $text = ($log | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) {
    $out["message"] = "auto_commit_push failed ($LASTEXITCODE): $text"
  } else {
    $out["message"] = if ($text) { $text } else { "auto_commit_push executed" }
  }
} catch {
  $out["message"] = "auto_commit_push skipped: $($_.Exception.Message)"
}

$out | ConvertTo-Json -Compress
