param(
    [string]$RunId = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = "precheck_" + [guid]::NewGuid().ToString("N")
}

if ($RunId -notmatch '^[A-Za-z0-9_-]{8,80}$') {
    throw "Invalid PRECHECK_TEST_RUN_ID"
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$previousLocation = Get-Location

# Не оставлять прежнюю конфигурацию после неуспешного bootstrap.
Remove-Item Env:PRECHECK_PG_DSN -ErrorAction SilentlyContinue
Remove-Item Env:PRECHECK_TEST_RUN_ID -ErrorAction SilentlyContinue
Remove-Item Env:PRECHECK_PROBE_DATABASE_URL -ErrorAction SilentlyContinue

try {
    Set-Location $here

    docker compose -f docker-compose.yml up -d
    if ($LASTEXITCODE -ne 0) {
        throw "Docker compose startup failed"
    }

    $ready = $false
    $deadline = (Get-Date).AddSeconds(60)

    do {
        Start-Sleep -Seconds 2

        docker compose -f docker-compose.yml exec -T precheck-pg `
            pg_isready -U sfrfr -d sfrfr_precheck *> $null

        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
    } while ((Get-Date) -lt $deadline)

    if (-not $ready) {
        throw "precheck-pg not ready"
    }

    Get-Content -Raw "$here\schema.sql" |
        docker compose -f docker-compose.yml exec -T precheck-pg `
            psql -U sfrfr -d sfrfr_precheck -v ON_ERROR_STOP=1

    if ($LASTEXITCODE -ne 0) {
        throw "Precheck schema bootstrap failed"
    }

    $guardSql = @"
CREATE SCHEMA IF NOT EXISTS precheck_test_guard;

CREATE TABLE IF NOT EXISTS precheck_test_guard.environment (
    singleton boolean PRIMARY KEY CHECK (singleton),
    run_id text NOT NULL
);

INSERT INTO precheck_test_guard.environment(singleton, run_id)
VALUES (TRUE, '$RunId')
ON CONFLICT (singleton)
DO UPDATE SET run_id = EXCLUDED.run_id;
"@

    $guardSql |
        docker compose -f docker-compose.yml exec -T precheck-pg `
            psql -U sfrfr -d sfrfr_precheck -v ON_ERROR_STOP=1

    if ($LASTEXITCODE -ne 0) {
        throw "Precheck guard bootstrap failed"
    }

    # Публичные credentials исключительно локального harness.
    $env:PRECHECK_PG_DSN = `
        "postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"

    $env:PRECHECK_TEST_RUN_ID = $RunId

    Write-Host "Precheck local harness ready"
    Write-Host "PRECHECK_PG_DSN set (credentials hidden)"
    Write-Host "PRECHECK_TEST_RUN_ID=$RunId"
}
finally {
    Set-Location $previousLocation
}
