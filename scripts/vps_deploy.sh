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

# Кабинеты Next.js (если unit-файлы установлены)
if systemctl list-unit-files | grep -q '^sfrfr-cabinet\.service'; then
  if [[ -d "$APP_DIR/apps/cabinet" ]]; then
    sudo -u "$APP_USER" bash -lc "
      cd '$APP_DIR/apps/cabinet'
      if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
      npm run build
    "
    systemctl restart sfrfr-cabinet || true
  fi
fi
if systemctl list-unit-files | grep -q '^sfrfr-admin\.service'; then
  if [[ -d "$APP_DIR/apps/admin" ]]; then
    sudo -u "$APP_USER" bash -lc "
      cd '$APP_DIR/apps/admin'
      if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
      npm run build
    "
    systemctl restart sfrfr-admin || true
  fi
fi

curl -fsS "http://127.0.0.1:8011/health" >/dev/null
echo "Deploy OK: $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
