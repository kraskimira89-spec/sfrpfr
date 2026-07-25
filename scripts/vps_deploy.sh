#!/usr/bin/env bash
# Обновление кода на VPS (вызывается из GitHub Actions или вручную).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
APP_USER="${APP_USER:-sfrfr}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"
# Файлы, созданные от root (WP seed и т.п.), ломают git reset от sfrfr
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
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
rebuild_next_app() {
  local name="$1"
  local dir="$2"
  local unit="$3"
  if [[ ! -f "/etc/systemd/system/${unit}" ]] && ! systemctl cat "$unit" >/dev/null 2>&1; then
    echo "Skip $name: no systemd unit $unit"
    return 0
  fi
  if [[ ! -d "$dir" ]]; then
    echo "Skip $name: missing $dir"
    return 0
  fi
  echo "Building $name in $dir …"
  sudo -u "$APP_USER" bash -lc "
    set -euo pipefail
    cd '$dir'
    export PATH=\"\$HOME/.nvm/versions/node/\$(ls \"\$HOME/.nvm/versions/node\" 2>/dev/null | tail -1)/bin:/usr/local/bin:\$PATH\"
    command -v npm >/dev/null
    if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
    npm run build
  "
  systemctl restart "$unit"
  systemctl is-active --quiet "$unit"
  echo "OK $name restarted"
}

rebuild_next_app "cabinet" "$APP_DIR/apps/cabinet" "sfrfr-cabinet.service"
rebuild_next_app "admin" "$APP_DIR/apps/admin" "sfrfr-admin.service"

curl -fsS "http://127.0.0.1:8011/health" >/dev/null
echo "Deploy OK: $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
