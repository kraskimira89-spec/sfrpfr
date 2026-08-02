# Ждать DNS supabase → staging IP и проверить HTTPS (Caddy/ACME).
param(
  [string]$HostName = "supabase.proverkastaza.ru",
  [string]$ExpectIp = "51.250.13.240",
  [int]$TimeoutSec = 900,
  [int]$PollSec = 30
)

$ErrorActionPreference = "Stop"
$deadline = (Get-Date).AddSeconds($TimeoutSec)

Write-Host "Waiting DNS $HostName -> $ExpectIp (timeout ${TimeoutSec}s)..."
while ((Get-Date) -lt $deadline) {
  try {
    $answers = Resolve-DnsName -Name $HostName -Type A -Server 8.8.8.8 -ErrorAction Stop |
      Where-Object { $_.Type -eq "A" } |
      Select-Object -ExpandProperty IPAddress
  } catch {
    $answers = @()
  }
  if ($answers -contains $ExpectIp) {
    Write-Host "DNS OK: $($answers -join ', ')"
    break
  }
  Write-Host "  now: $(if ($answers) { $answers -join ', ' } else { 'NXDOMAIN/empty' })"
  Start-Sleep -Seconds $PollSec
}
if (-not ($answers -contains $ExpectIp)) {
  throw "DNS not ready for $HostName"
}

Write-Host "Restart Caddy on VM to retry ACME..."
ssh -o BatchMode=yes sfrfr@$ExpectIp `
  "cd /opt/sfrfr-supabase/supabase/docker && docker compose restart caddy"

Write-Host "Waiting HTTPS 200/401/404 on https://$HostName/ ..."
while ((Get-Date) -lt $deadline) {
  try {
    $code = curl.exe -sS -o NUL -w "%{http_code}" --connect-timeout 10 "https://$HostName/"
  } catch {
    $code = "000"
  }
  Write-Host "  https status=$code"
  if ($code -match '^(200|301|302|401|404)$') {
    Write-Host "TLS OK"
    exit 0
  }
  Start-Sleep -Seconds $PollSec
}
throw "HTTPS not ready for $HostName"
