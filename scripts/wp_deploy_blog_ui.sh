#!/usr/bin/env bash
# Deploy ТЗ-11 §13 blog UI to WordPress MU-plugins on VPS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WP_CONTENT="${WP_CONTENT:-/var/www/taxi-doroga-dobra/wp-content}"
WP_ROOT="${WP_ROOT:-$(dirname "${WP_CONTENT}")}"
MU="${WP_CONTENT}/mu-plugins"
ASSETS_SRC="${ROOT}/scripts/assets/blog/ui"
ASSETS_DST="${MU}/sfrfr-blog-ui-assets"

mkdir -p "${MU}" "${ASSETS_DST}"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-blog-ui.php" "${MU}/sfrfr-blog-ui.php"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-blog-ui-empty-comments.php" "${MU}/sfrfr-blog-ui-empty-comments.php"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-seo-meta.php" "${MU}/sfrfr-seo-meta.php"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-hide-astra-copyright.php" "${MU}/sfrfr-hide-astra-copyright.php"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-site-footer.php" "${MU}/sfrfr-site-footer.php"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-yandex-verification.php" "${MU}/sfrfr-yandex-verification.php"
cp -f "${ASSETS_SRC}/blog-ui.css" "${ASSETS_DST}/blog-ui.css"
cp -f "${ASSETS_SRC}/blog-ui.js" "${ASSETS_DST}/blog-ui.js"

if command -v wp >/dev/null 2>&1 && [[ -f "${WP_ROOT}/wp-config.php" ]]; then
  wp --path="${WP_ROOT}" --allow-root cache flush || echo "WARN: WP object cache flush failed"
  wp --path="${WP_ROOT}" --allow-root super-cache flush 2>/dev/null || true
fi

echo "OK: ${MU}/sfrfr-blog-ui.php"
echo "OK: ${MU}/sfrfr-seo-meta.php"
echo "OK: ${MU}/sfrfr-hide-astra-copyright.php"
echo "OK: ${MU}/sfrfr-site-footer.php"
echo "OK: ${ASSETS_DST}/"
