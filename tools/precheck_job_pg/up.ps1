# Поднять одноразовый Postgres + PostgREST для precheck (55432 / 55433).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
docker compose -f docker-compose.yml up -d
$deadline = (Get-Date).AddSeconds(90)
do {
  Start-Sleep -Seconds 2
  $ok = docker compose -f docker-compose.yml exec -T precheck-pg pg_isready -U sfrfr -d sfrfr_precheck 2>$null
  if ($LASTEXITCODE -eq 0) { break }
} while ((Get-Date) -lt $deadline)
if ($LASTEXITCODE -ne 0) { throw "precheck-pg not ready" }
Get-Content -Raw "$here\schema.sql" | docker compose -f docker-compose.yml exec -T precheck-pg psql -U sfrfr -d sfrfr_precheck -v ON_ERROR_STOP=1

$restDeadline = (Get-Date).AddSeconds(60)
do {
  Start-Sleep -Seconds 2
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:55433/" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -ge 200) { break }
  } catch {
    # ждём health
  }
} while ((Get-Date) -lt $restDeadline)

Write-Host "PRECHECK_PG_DSN=postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
Write-Host "PRECHECK_POSTGREST_URL=http://127.0.0.1:55433"
Write-Host "PRECHECK_POSTGREST_JWT_SECRET=precheck-e2e-jwt-secret-local-only-not-prod"
