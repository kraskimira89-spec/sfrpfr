#!/usr/bin/env bash
# Автоисправления для диагностики Яндекс Вебмастера на VPS.
# Вызывается из yandex_webmaster_diagnostics.py --fix --ssh и из GH Actions.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
WP="wp --path=${SITE_DIR} --allow-root"

echo "==> git pull"
cd "$ROOT"
git pull --ff-only origin main

echo "==> MU: metrika + robots"
sudo SITE_DIR="$SITE_DIR" ENVF="${ENVF:-/opt/sfrfr/.env}" bash "$ROOT/scripts/wp_deploy_metrika.sh"

echo "==> MU: blog UI + seo meta"
sudo WP_ROOT="$SITE_DIR" bash "$ROOT/scripts/wp_deploy_blog_ui.sh"

echo "==> favicons in site root"
for f in favicon.ico favicon.svg favicon-120.png; do
  if [[ -f "$ROOT/scripts/assets/$f" ]]; then
    cp -f "$ROOT/scripts/assets/$f" "$SITE_DIR/$f"
    chown www-data:www-data "$SITE_DIR/$f" 2>/dev/null || true
    echo "OK: $SITE_DIR/$f"
  fi
done

echo "==> webmaster ensure (sitemap API)"
if [[ -f "$ROOT/secrets/yandex-webmaster.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/secrets/yandex-webmaster.env"
  set +a
  PY="${ROOT}/.venv/bin/python"
  [[ -x "$PY" ]] || PY=python3
  "$PY" "$ROOT/scripts/yandex_webmaster_ensure_site.py" || echo "WARN: ensure_site"
else
  echo "SKIP: no secrets/yandex-webmaster.env on VPS"
fi

echo "==> cache flush"
$WP cache flush 2>/dev/null || true
rm -rf "$SITE_DIR/wp-content/cache/supercache/"* 2>/dev/null || true

echo "==> live probes"
curl -fsS -o /dev/null -w "robots.txt %{http_code}\n" "https://proverkastaza.ru/robots.txt"
curl -fsS -o /dev/null -w "sitemap %{http_code}\n" "https://proverkastaza.ru/wp-sitemap.xml"
curl -fsS -o /dev/null -w "home %{http_code}\n" "https://proverkastaza.ru/"
curl -fsSI "https://proverkastaza.ru/favicon.ico" | head -3

echo "OK: vps_webmaster_remediate"
