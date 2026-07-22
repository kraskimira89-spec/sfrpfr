#!/usr/bin/env pwsh
<#
.SYNOPSIS
  1) Создаёт SSH-ключ для GitHub Actions → VPS
  2) Пишет секреты VPS_* в GitHub (gh secret set)
  3) Печатает команды для bootstrap на VPS

.EXAMPLE
  .\scripts\setup_github_vps_secrets.ps1 -VpsHost 1.2.3.4 -VpsUser root
#>
param(
  [Parameter(Mandatory = $true)][string]$VpsHost,
  [Parameter(Mandatory = $true)][string]$VpsUser,
  [string]$VpsPort = "22",
  [string]$Repo = "kraskimira89-spec/sfrpfr",
  [string]$KeyDir = "",
  [switch]$SkipGithubSecrets
)

$ErrorActionPreference = "Stop"

if (-not $KeyDir) {
  $KeyDir = Join-Path $env:USERPROFILE ".ssh\sfrfr-deploy"
}
New-Item -ItemType Directory -Force -Path $KeyDir | Out-Null

$privateKey = Join-Path $KeyDir "id_ed25519_sfrfr_deploy"
$publicKey = "$privateKey.pub"

if (-not (Test-Path $privateKey)) {
  Write-Host "==> Generating deploy key: $privateKey"
  ssh-keygen -t ed25519 -f $privateKey -N '""' -C "github-actions-sfrfr-deploy"
} else {
  Write-Host "==> Reusing existing key: $privateKey"
}

$pub = (Get-Content $publicKey -Raw).Trim()
$priv = Get-Content $privateKey -Raw

Write-Host ""
Write-Host "========== PUBLIC KEY (add to VPS ~/.ssh/authorized_keys for user $VpsUser) =========="
Write-Host $pub
Write-Host "====================================================================================="
Write-Host ""

if (-not $SkipGithubSecrets) {
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "gh CLI not found"
  }
  Write-Host "==> Setting GitHub Actions secrets on $Repo"
  $VpsHost | gh secret set VPS_HOST -R $Repo
  $VpsUser | gh secret set VPS_USER -R $Repo
  $VpsPort | gh secret set VPS_PORT -R $Repo
  $priv | gh secret set VPS_SSH_KEY -R $Repo
  Write-Host "Secrets set: VPS_HOST, VPS_USER, VPS_PORT, VPS_SSH_KEY"
  gh secret list -R $Repo
}

Write-Host ""
Write-Host "========== NEXT: on VPS (SSH as $VpsUser@$VpsHost) =========="
Write-Host @"
# 1) Allow GitHub Actions key
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo '$pub' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 2) Packages
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip

# 3) Deploy key for cloning GitHub AS user sfrfr (read-only)
#    Option A (HTTPS + token) — simpler for first bootstrap:
#    leave REPO_URL as HTTPS and use a fine-grained PAT with Contents:Read
#    Option B: create deploy key in GitHub repo Settings → Deploy keys

# 4) Bootstrap app dir /opt/sfrfr
cd /tmp
git clone https://github.com/kraskimira89-spec/sfrpfr.git sfrpfr-tmp
cd sfrpfr-tmp
sudo REPO_URL=https://github.com/kraskimira89-spec/sfrpfr.git \
  APP_DIR=/opt/sfrfr \
  APP_USER=sfrfr \
  bash scripts/vps_bootstrap.sh

# 5) Passwordless sudo for deploy user ($VpsUser) — adjust username
echo '$VpsUser ALL=(root) NOPASSWD: /bin/bash /opt/sfrfr/scripts/vps_deploy.sh, /bin/systemctl restart sfrfr-api, /bin/systemctl is-active sfrfr-api' | sudo tee /etc/sudoers.d/sfrfr-deploy
sudo chmod 440 /etc/sudoers.d/sfrfr-deploy

# 6) Fill secrets
sudo nano /opt/sfrfr/.env
sudo systemctl restart sfrfr-api
sudo systemctl status sfrfr-api
"@
Write-Host "==============================================================="
Write-Host ""
Write-Host "Test SSH from this PC:"
Write-Host "  ssh -i `"$privateKey`" -p $VpsPort $VpsUser@$VpsHost"
Write-Host ""
Write-Host "After bootstrap, trigger deploy:"
Write-Host "  gh workflow run deploy-vps.yml -R $Repo"
