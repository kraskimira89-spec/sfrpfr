# Деплой SmartCaptcha на WP + Auth email hook на staging Supabase.
param(
  [string]$VmHost = "sfrfr@51.250.13.240",
  [string]$VpsHost = "root@91.229.11.147"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-DotEnvValue([string]$Path, [string]$Key) {
  $line = Get-Content $Path -ErrorAction SilentlyContinue | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -First 1
  if (-not $line) { return "" }
  return ($line -replace "^$([regex]::Escape($Key))=", "").Trim().Trim('"')
}

$hookSecret = Get-DotEnvValue ".env" "SUPABASE_SEND_EMAIL_HOOK_SECRET"
if (-not $hookSecret) {
  throw "SUPABASE_SEND_EMAIL_HOOK_SECRET missing in .env"
}

$tmpSecret = Join-Path $env:TEMP "sfrfr-hook-secret.txt"
Set-Content -Path $tmpSecret -Value $hookSecret -NoNewline -Encoding ascii

Write-Host "== staging: auth email hook =="
scp -o BatchMode=yes `
  scripts/assets/docker-compose.sfrfr-email.yml `
  scripts/vm_supabase_enable_auth_email_hook.sh `
  $tmpSecret `
  "${VmHost}:/tmp/"
Remove-Item $tmpSecret -Force

ssh -o BatchMode=yes $VmHost @'
set -euo pipefail
chmod +x /tmp/vm_supabase_enable_auth_email_hook.sh
export GOTRUE_HOOK_SEND_EMAIL_SECRETS="$(cat /tmp/sfrfr-hook-secret.txt)"
rm -f /tmp/sfrfr-hook-secret.txt
OVERLAY_SRC=/tmp/docker-compose.sfrfr-email.yml /tmp/vm_supabase_enable_auth_email_hook.sh
'@

Write-Host "== VPS: git pull + SmartCaptcha WP =="
ssh -o BatchMode=yes $VpsHost @'
set -euo pipefail
cd /opt/sfrfr
git pull --ff-only origin main
SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_apply_landing_vps.sh
if [ -d /var/www/html/wp-content/mu-plugins ]; then
  cp -f /var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-recaptcha-lead.php /var/www/html/wp-content/mu-plugins/ || true
  cp -f /var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-recaptcha-lead.js /var/www/html/wp-content/mu-plugins/ || true
  cp -f /var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-lead.config.php /var/www/html/wp-content/mu-plugins/ || true
fi
systemctl restart sfrfr-api
sleep 2
systemctl is-active sfrfr-api
test -f /var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-lead.config.php
php -r '$c=include "/var/www/taxi-doroga-dobra/wp-content/mu-plugins/sfrfr-lead.config.php"; echo "clientKey_prefix=".substr($c["SMARTCAPTCHA_CLIENT_KEY"]??"",0,5)." len=".strlen($c["SMARTCAPTCHA_CLIENT_KEY"]??"")."\n";'
grep -E "^(CAPTCHA_PROVIDER)=" /opt/sfrfr/.env
'@

Write-Host "DONE"
