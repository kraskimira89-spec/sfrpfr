#!/usr/bin/env bash
# Деплой MU-plugin Яндекс Метрики на WP.
# Требует YANDEX_METRIKA_COUNTER_ID в /opt/sfrfr/.env
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
MU="${SITE_DIR}/wp-content/mu-plugins"
ENVF="${ENVF:-/opt/sfrfr/.env}"

mkdir -p "$MU"
cp -f "$ROOT/scripts/wp-mu-plugins/sfrfr-yandex-metrika.php" "$MU/sfrfr-yandex-metrika.php"
chown www-data:www-data "$MU/sfrfr-yandex-metrika.php" 2>/dev/null || true

cid=""
if [[ -f "$ENVF" ]]; then
  cid="$(grep -E '^YANDEX_METRIKA_COUNTER_ID=' "$ENVF" | head -n1 | cut -d= -f2- | tr -d '\"' | tr -d "'" || true)"
fi
if [[ -z "${cid// }" ]]; then
  echo "WARN: YANDEX_METRIKA_COUNTER_ID пуст в $ENVF — плагин на сайте, счётчик не рисуется."
else
  echo "OK: metrika MU deployed; counter_id=$cid"
fi
