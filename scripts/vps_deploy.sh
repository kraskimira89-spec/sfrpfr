#!/usr/bin/env bash
# Обновление кода на VPS (вызывается из GitHub Actions или вручную).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
APP_USER="${APP_USER:-sfrfr}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"
sudo -u "$APP_USER" git fetch origin
sudo -u "$APP_USER" git reset --hard "origin/$BRANCH"

sudo -u "$APP_USER" bash -lc "
  cd '$APP_DIR'
  . .venv/bin/activate
  pip install -e '.[ai]' -q
"

systemctl restart sfrfr-api
systemctl is-active --quiet sfrfr-api
echo "Deploy OK: $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
