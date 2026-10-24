# Поднять одноразовый Postgres + PostgREST (55432 / 55433) и маркер run_id.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
# up.ps1 → tools/precheck_job_pg → repo root
$repo = (Resolve-Path (Join-Path $here "..\..")).Path
Push-Location $here
try {
  docker compose -f docker-compose.yml up -d
  $deadline = (Get-Date).AddSeconds(90)
  do {
    Start-Sleep -Seconds 2
    $ok = docker compose -f docker-compose.yml exec -T precheck-pg pg_isready -U sfrfr -d sfrfr_precheck 2>$null
    if ($LASTEXITCODE -eq 0) { break }
  } while ((Get-Date) -lt $deadline)
  if ($LASTEXITCODE -ne 0) { throw "precheck-pg not ready" }
  Get-Content -Raw "$here\schema.sql" | docker compose -f docker-compose.yml exec -T precheck-pg psql -U sfrfr -d sfrfr_precheck -v ON_ERROR_STOP=1

  if (-not $env:PRECHECK_TEST_RUN_ID) {
    $env:PRECHECK_TEST_RUN_ID = "precheck_" + [guid]::NewGuid().ToString("N").Substring(0, 16)
  }
  $runId = $env:PRECHECK_TEST_RUN_ID
  if ($runId -notmatch '^[A-Za-z0-9_-]{8,80}$') {
    throw "invalid PRECHECK_TEST_RUN_ID"
  }
  $sql = @"
INSERT INTO precheck_test_guard.environment(singleton, run_id)
VALUES (TRUE, '$runId')
ON CONFLICT (singleton) DO UPDATE SET run_id = EXCLUDED.run_id;
INSERT INTO public.sfrfr_test_run(run_id) VALUES ('$runId')
ON CONFLICT (run_id) DO NOTHING;
"@
  $sql | docker compose -f docker-compose.yml exec -T precheck-pg psql -U sfrfr -d sfrfr_precheck -v ON_ERROR_STOP=1

  $restDeadline = (Get-Date).AddSeconds(60)
  do {
    Start-Sleep -Seconds 2
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:55433/" -UseBasicParsing -TimeoutSec 3
      if ($r.StatusCode -ge 200) { break }
    } catch { }
  } while ((Get-Date) -lt $restDeadline)
}
finally {
  Set-Location $repo
}

$env:PRECHECK_PG_DSN = "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
Remove-Item Env:PRECHECK_PROBE_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

Write-Host "PRECHECK_PG_DSN=$env:PRECHECK_PG_DSN"
Write-Host "PRECHECK_TEST_RUN_ID=$env:PRECHECK_TEST_RUN_ID"
Write-Host "PRECHECK_POSTGREST_URL=http://127.0.0.1:55433"
Write-Host "cwd_restored=$repo"
