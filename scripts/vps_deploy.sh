#!/usr/bin/env bash
# Обновление кода на VPS (вызывается из GitHub Actions или вручную).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
APP_USER="${APP_USER:-sfrfr}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"

# После git reset нужно перезапустить ЭТУ же копию скрипта с диска,
# иначе bash продолжает старую версию (без пересборки Next.js).
if [[ "${1:-}" != "--post-update" ]]; then
  chown -R "$APP_USER:$APP_USER" "$APP_DIR"
  sudo -u "$APP_USER" git fetch origin
  sudo -u "$APP_USER" git reset --hard "origin/$BRANCH"
  exec bash "$APP_DIR/scripts/vps_deploy.sh" --post-update
fi

sudo -u "$APP_USER" bash -lc "
  cd '$APP_DIR'
  . .venv/bin/activate
  pip install -e '.[ai]' -q
"

systemctl restart sfrfr-api
systemctl is-active --quiet sfrfr-api

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
    export PATH=\"/usr/local/bin:/usr/bin:\$PATH\"
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

# ТЗ-11 §13: чипы/TOC/CTA блога в WordPress MU-plugins
if [[ -x "$APP_DIR/scripts/wp_deploy_blog_ui.sh" ]] || [[ -f "$APP_DIR/scripts/wp_deploy_blog_ui.sh" ]]; then
  echo "Deploying blog UI §13 …"
  bash "$APP_DIR/scripts/wp_deploy_blog_ui.sh" || echo "WARN: wp_deploy_blog_ui.sh failed (WP path?)"
fi

# Главная + CSS + футер CTA (ТЗ-20/21: «Уточнить ситуацию в MAX»)
if [[ -f "$APP_DIR/scripts/wp_apply_landing_vps.sh" ]]; then
  echo "Applying WP landing (home/CTA) …"
  bash "$APP_DIR/scripts/wp_apply_landing_vps.sh" || echo "WARN: wp_apply_landing_vps.sh failed"
fi

if [[ -f "$APP_DIR/scripts/wp_deploy_yandex_business_price.sh" ]]; then
  echo "Deploying Yandex Business price YML …"
  bash "$APP_DIR/scripts/wp_deploy_yandex_business_price.sh" || echo "WARN: wp_deploy_yandex_business_price.sh failed"
fi

if [[ -f "$APP_DIR/scripts/wp_deploy_yandex_review_qr.sh" ]]; then
  echo "Deploying Yandex review QR …"
  bash "$APP_DIR/scripts/wp_deploy_yandex_review_qr.sh" || echo "WARN: wp_deploy_yandex_review_qr.sh failed"
fi

# ТЗ-18/19: страницы доверия/контактов (в т.ч. блок отзывов)
if [[ -f "$APP_DIR/scripts/wp_seed_trust_pages_tz18.sh" ]]; then
  echo "Seeding trust/commerce pages …"
  bash "$APP_DIR/scripts/wp_seed_trust_pages_tz18.sh" || echo "WARN: wp_seed_trust_pages_tz18.sh failed"
fi

# Яндекс Метрика (счётчик из YANDEX_METRIKA_COUNTER_ID)
if [[ -f "$APP_DIR/scripts/wp_deploy_metrika.sh" ]]; then
  echo "Deploying Yandex Metrika MU …"
  bash "$APP_DIR/scripts/wp_deploy_metrika.sh" || echo "WARN: wp_deploy_metrika.sh failed"
fi

# Мини-приложение MAX → https://proverkastaza.ru/app/
if [[ -f "$APP_DIR/scripts/deploy_max_miniapp.sh" ]]; then
  echo "Deploying MAX miniapp /app/ …"
  bash "$APP_DIR/scripts/deploy_max_miniapp.sh" || echo "WARN: deploy_max_miniapp.sh failed"
fi

curl -fsS "http://127.0.0.1:8011/health" >/dev/null
echo "Deploy OK: $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
