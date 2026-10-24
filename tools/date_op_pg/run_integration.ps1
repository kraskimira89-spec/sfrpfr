# Поднять изолированный PG и прогнать date-op integration.
# Требует Docker Desktop / docker engine. Не трогает prod.

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

$Compose = "tools/date_op_pg/docker-compose.yml"
$Dsn = "postgresql://sfrfr:sfrfr_test@127.0.0.1:15433/sfrfr_date_op_test"

Write-Host "docker compose up (port 15433)..."
docker compose -f $Compose up -d --wait

$env:DATABASE_URL = $Dsn
Write-Host "bootstrap schema..."
& .\.venv\Scripts\python.exe tools\date_op_pg\bootstrap_schema.py

Write-Host "pytest integration..."
& .\.venv\Scripts\python.exe -m pytest `
  tests/integration/test_period_date_correction_pg.py -q `
  --basetemp=tmp/pytest-date-op-pg

Write-Host "done. stop: docker compose -f $Compose down -v"
