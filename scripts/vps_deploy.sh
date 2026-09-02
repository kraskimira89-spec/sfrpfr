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
  # HTTPS fetch с VPS иногда даёт 128; 3 попытки. Не задавать GIT_ASKPASS —
  # пустой Basic auth → HTTP 401 от GitHub на публичный репозиторий.
  fetch_ok=0
  for _try in 1 2 3; do
    if sudo -u "$APP_USER" env GIT_TERMINAL_PROMPT=0 \
      git -C "$APP_DIR" -c credential.helper= fetch --prune origin; then
      fetch_ok=1
      break
    fi
    echo "WARN: git fetch failed (try ${_try}/3), retry…"
    sleep 2
  done
  if [[ "$fetch_ok" -ne 1 ]]; then
    echo "ERROR: git fetch origin failed after retries"
    exit 1
  fi
  sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BRANCH"
  exec bash "$APP_DIR/scripts/vps_deploy.sh" --post-update
fi

sudo -u "$APP_USER" bash -lc "
  cd '$APP_DIR'
  . .venv/bin/activate
  pip install -e '.[ai]' -q
"

systemctl restart sfrfr-api
systemctl is-active --quiet sfrfr-api

if [[ -f "$APP_DIR/docs/systemd/sfrfr-document-ingest.service" ]]; then
  echo "Configuring document ingest worker …"
  install -m 0644 "$APP_DIR/docs/systemd/sfrfr-document-ingest.service" \
    /etc/systemd/system/sfrfr-document-ingest.service
  systemctl daemon-reload
  systemctl enable --now sfrfr-document-ingest.service
  systemctl is-active --quiet sfrfr-document-ingest.service
fi

if [[ -f "$APP_DIR/docs/systemd/sfrfr-case-chat-outbox.service" ]]; then
  echo "Configuring case chat outbox + bot jobs worker …"
  install -m 0644 "$APP_DIR/docs/systemd/sfrfr-case-chat-outbox.service" \
    /etc/systemd/system/sfrfr-case-chat-outbox.service
  systemctl daemon-reload
  systemctl enable --now sfrfr-case-chat-outbox.service
  systemctl restart sfrfr-case-chat-outbox.service
  systemctl is-active --quiet sfrfr-case-chat-outbox.service
fi

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
  # Ручной деплой или CI могут оставить .next/node_modules от root → EACCES при npm run build.
  chown -R "$APP_USER:$APP_USER" "$dir"
  # На VPS ~2 GiB RAM: без swap npm ci/next часто получают SIGKILL (137).
  # Повторно не гоняем npm ci, если package-lock не менялся.
  sudo -u "$APP_USER" bash -lc "
    set -euo pipefail
    cd '$dir'
    export PATH=\"/usr/local/bin:/usr/bin:\$PATH\"
    export NODE_OPTIONS=\"\${NODE_OPTIONS:---max-old-space-size=768}\"
    export npm_config_jobs=\"\${npm_config_jobs:-1}\"
    command -v npm >/dev/null
    lock_stamp=.deploy-package-lock.sha256
    need_ci=1
    if [[ -f package-lock.json ]]; then
      lock_hash=\$(sha256sum package-lock.json | awk '{print \$1}')
      if [[ -d node_modules ]] && [[ -f \"\$lock_stamp\" ]] && [[ \"\$(cat \"\$lock_stamp\")\" == \"\$lock_hash\" ]]; then
        need_ci=0
        echo \"Reuse node_modules for $name (lock unchanged)\"
      fi
    fi
    if [[ \"\$need_ci\" -eq 1 ]]; then
      if [[ -f package-lock.json ]]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
      if [[ -n \"\${lock_hash:-}\" ]]; then echo \"\$lock_hash\" > \"\$lock_stamp\"; fi
    fi
    rm -rf .next
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

# BVI: версия для слабовидящих
if [[ -f "$APP_DIR/scripts/wp_ensure_bvi.sh" ]]; then
  echo "Ensuring BVI accessibility plugin …"
  bash "$APP_DIR/scripts/wp_ensure_bvi.sh" || echo "WARN: wp_ensure_bvi.sh failed"
fi

if [[ -f "$APP_DIR/scripts/wp_deploy_yandex_business_price.sh" ]]; then
  echo "Deploying Yandex Business price YML …"
  bash "$APP_DIR/scripts/wp_deploy_yandex_business_price.sh" || echo "WARN: wp_deploy_yandex_business_price.sh failed"
fi

if [[ -f "$APP_DIR/scripts/wp_deploy_yandex_review_qr.sh" ]]; then
  echo "Deploying Yandex review QR …"
  bash "$APP_DIR/scripts/wp_deploy_yandex_review_qr.sh" || echo "WARN: wp_deploy_yandex_review_qr.sh failed"
fi

if [[ -f "$APP_DIR/scripts/wp_deploy_leadmagnet_a4_pdf.sh" ]]; then
  echo "Deploying lead magnet A4 PDF …"
  bash "$APP_DIR/scripts/wp_deploy_leadmagnet_a4_pdf.sh" || echo "WARN: wp_deploy_leadmagnet_a4_pdf.sh failed"
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
