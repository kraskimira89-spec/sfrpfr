# Переключить prod VPS API/cabinet/admin на self-host Supabase (YC).
# Требует: secrets/supabase-staging.env, SSH root@VPS.
param(
  [string]$Vps = "root@91.229.11.147",
  [string]$StagingEnv = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $StagingEnv) { $StagingEnv = Join-Path $Root "secrets\supabase-staging.env" }
if (-not (Test-Path $StagingEnv)) { throw "Missing $StagingEnv" }

$kv = @{}
Get-Content $StagingEnv | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
  $k, $v = $_.Split('=', 2)
  $kv[$k.Trim()] = $v.Trim()
}
foreach ($req in @("ANON_KEY", "SERVICE_ROLE_KEY", "API_EXTERNAL_URL")) {
  if (-not $kv.ContainsKey($req) -or -not $kv[$req]) { throw "Missing $req in staging env" }
}

$url = $kv["API_EXTERNAL_URL"]
$anon = $kv["ANON_KEY"]
$service = $kv["SERVICE_ROLE_KEY"]
$dbPass = $kv["POSTGRES_PASSWORD"]
# Direct DB only on VM; API uses Supabase URL. Optional DATABASE_URL via pooler if exposed.
# Keep DATABASE_URL pointing to YC only if we publish it; otherwise leave API on REST/service role.
Write-Host "Target SUPABASE_URL=$url"

$tmp = Join-Path $env:TEMP "sfrfr-supabase-cutover.env"
@"
SUPABASE_URL=$url
SUPABASE_ANON_KEY=$anon
SUPABASE_SERVICE_ROLE_KEY=$service
NEXT_PUBLIC_SUPABASE_URL=$url
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$anon
"@ | Set-Content -Path $tmp -Encoding utf8

scp -o BatchMode=yes $tmp "${Vps}:/tmp/sfrfr-supabase-cutover.env"
scp -o BatchMode=yes (Join-Path $Root "scripts\vps_apply_supabase_yc_env.sh") "${Vps}:/tmp/vps_apply_supabase_yc_env.sh"

ssh -o BatchMode=yes $Vps @"
set -e
chmod +x /tmp/vps_apply_supabase_yc_env.sh
bash /tmp/vps_apply_supabase_yc_env.sh /tmp/sfrfr-supabase-cutover.env
rm -f /tmp/sfrfr-supabase-cutover.env
"@

Remove-Item $tmp -Force
Write-Host "DONE VPS switch"
