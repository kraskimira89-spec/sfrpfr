#!/usr/bin/env pwsh
# Cursor stop-hook: автокоммит и пуш после завершения агента.
# Читает JSON со stdin (игнорируем), пишет JSON-ответ в stdout.
$ErrorActionPreference = "Continue"
try {
  $null = [Console]::In.ReadToEnd()
} catch {}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$out = @{ continue = $true }
try {
  & "$repoRoot\scripts\auto_commit_push.ps1" -Message "AUTO: agent stop $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>&1 | Out-Null
  $out["message"] = "auto_commit_push executed"
} catch {
  $out["message"] = "auto_commit_push skipped: $($_.Exception.Message)"
}

$out | ConvertTo-Json -Compress
