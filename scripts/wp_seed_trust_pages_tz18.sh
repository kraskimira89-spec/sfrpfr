#!/usr/bin/env bash
# ТЗ-18 этап 2: страницы доверия/коммерции на VPS.
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_trust_pages_tz18.sh
set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

export SFRFR_TRUST_ASSETS="${SCRIPT_DIR}/assets/trust"
export MAX_CHAT_URL="${MAX_CHAT_URL:-${MAX_PUBLIC_BOT_URL:-https://max.ru/id8905998693_1_bot}}"

echo "==> Deploy expert photos + awards gallery"
UPLOADS="${SITE_DIR}/wp-content/uploads/sfrfr"
mkdir -p "${UPLOADS}/awards"
cp -f "${SCRIPT_DIR}/assets/trust/expert-lopakova.jpg" "${UPLOADS}/expert-lopakova.jpg"
cp -f "${SCRIPT_DIR}/assets/trust/expert-bogdanovskiy.jpg" "${UPLOADS}/expert-bogdanovskiy.jpg"
if compgen -G "${SCRIPT_DIR}/assets/awards/award-*.jpg" > /dev/null; then
  cp -f "${SCRIPT_DIR}/assets/awards/award-"*.jpg "${UPLOADS}/awards/"
fi
cp -f "${SCRIPT_DIR}/assets/sfrfr-awards.js" "${SITE_DIR}/wp-content/mu-plugins/sfrfr-awards.js"
chown -R www-data:www-data "${UPLOADS}" 2>/dev/null || true
chown www-data:www-data "${SITE_DIR}/wp-content/mu-plugins/sfrfr-awards.js" 2>/dev/null || true

echo "==> Seed trust/commerce pages"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_seed_trust_pages_tz18.php"

# Обновить ссылки на главной
if [[ -f "${SCRIPT_DIR}/wp_apply_home.php" ]]; then
  echo "==> Refresh home links"
  export SFRFR_HOME_PATH="${SCRIPT_DIR}/assets/sfrfr-home.html"
  "${WP[@]}" eval-file "${SCRIPT_DIR}/wp_apply_home.php" || echo "WARN: home apply failed"
fi

# MU: seo-meta + footer + metrika (byline/schema/goals)
MU="${SITE_DIR}/wp-content/mu-plugins"
mkdir -p "${MU}"
cp -f "${SCRIPT_DIR}/wp-mu-plugins/sfrfr-seo-meta.php" "${MU}/sfrfr-seo-meta.php"
cp -f "${SCRIPT_DIR}/wp-mu-plugins/sfrfr-site-footer.php" "${MU}/sfrfr-site-footer.php"
cp -f "${SCRIPT_DIR}/wp-mu-plugins/sfrfr-yandex-metrika.php" "${MU}/sfrfr-yandex-metrika.php"

"${WP[@]}" cache flush || true
"${WP[@]}" super-cache flush 2>/dev/null || true
echo "==> OK trust pages"
