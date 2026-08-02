# Деплой хвостов фазы 1 ТЗ-15 на staging ВМ (миграции, seed, backup, restore-drill, Caddy).
param(
  [string]$VmHost = "sfrfr@51.250.13.240",
  [switch]$SkipCaddy
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== scp scripts =="
scp -o BatchMode=yes `
  scripts/vm_supabase_enable_caddy.sh `
  scripts/vm_supabase_apply_migrations.sh `
  scripts/vm_supabase_backup.sh `
  scripts/vm_supabase_restore_drill.sh `
  scripts/staging_seed_synthetic.sql `
  "${VmHost}:/tmp/"

Write-Host "== scp migrations =="
ssh -o BatchMode=yes $VmHost "rm -rf /tmp/sfrfr-migrations && mkdir -p /tmp/sfrfr-migrations"
scp -o BatchMode=yes supabase/migrations/*.sql "${VmHost}:/tmp/sfrfr-migrations/"

Write-Host "== chmod + migrate =="
ssh -o BatchMode=yes $VmHost @"
set -e
chmod +x /tmp/vm_supabase_*.sh
sudo mkdir -p /data/backups/supabase-staging
sudo chown -R sfrfr:sfrfr /data/backups
MIG_DIR=/tmp/sfrfr-migrations SEED=/tmp/staging_seed_synthetic.sql /tmp/vm_supabase_apply_migrations.sh
"@

Write-Host "== backup + restore drill =="
ssh -o BatchMode=yes $VmHost @"
set -e
/tmp/vm_supabase_backup.sh
/tmp/vm_supabase_restore_drill.sh
"@

if (-not $SkipCaddy) {
  Write-Host "== caddy (needs DNS) =="
  ssh -o BatchMode=yes $VmHost "PROXY_DOMAIN=supabase.proverkastaza.ru /tmp/vm_supabase_enable_caddy.sh"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: caddy step failed (часто из-за DNS)"
  }
}

Write-Host "DONE"
