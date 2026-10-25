param()
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$previous = Get-Location

# Local-only (не prod).
$env:PRECHECK_AUTH_URL = "http://127.0.0.1:9999"
# Demo keys для local JWT secret (не prod).
$env:PRECHECK_AUTH_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
$env:PRECHECK_AUTH_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
$env:PRECHECK_AUTH_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
$env:PRECHECK_AUTH_INBUCKET = "http://127.0.0.1:9000"

try {
    Set-Location $here
    docker compose -f docker-compose.yml up -d
    if ($LASTEXITCODE -ne 0) {
        throw "BLOCKED: docker compose precheck_auth failed (exit $LASTEXITCODE)"
    }

    $ready = $false
    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Seconds 3
        try {
            $r = Invoke-WebRequest -Uri "$($env:PRECHECK_AUTH_URL)/health" -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                $ready = $true
                break
            }
        } catch {
            # still starting
        }
    } while ((Get-Date) -lt $deadline)

    if (-not $ready) {
        docker compose -f docker-compose.yml logs --tail 40 precheck-gotrue 2>&1 | Out-Host
        throw "BLOCKED: GoTrue http://127.0.0.1:9999/health not ready within 90s"
    }

    Write-Host "Precheck Auth ready"
    Write-Host "PRECHECK_AUTH_URL=$($env:PRECHECK_AUTH_URL)"
    Write-Host "Inbucket UI=$($env:PRECHECK_AUTH_INBUCKET)"
    Write-Host "Next: seed_staff_user.py + admin NEXT_PUBLIC_SUPABASE_URL=$($env:PRECHECK_AUTH_URL)"
}
finally {
    Set-Location $previous
}
