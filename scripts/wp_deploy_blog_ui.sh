#!/usr/bin/env bash
# Deploy ТЗ-11 §13 blog UI to WordPress MU-plugins on VPS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WP_CONTENT="${WP_CONTENT:-/var/www/taxi-doroga-dobra/wp-content}"
MU="${WP_CONTENT}/mu-plugins"
ASSETS_SRC="${ROOT}/scripts/assets/blog/ui"
ASSETS_DST="${MU}/sfrfr-blog-ui-assets"

mkdir -p "${MU}" "${ASSETS_DST}"
cp -f "${ROOT}/scripts/wp-mu-plugins/sfrfr-blog-ui.php" "${MU}/sfrfr-blog-ui.php"
cp -f "${ASSETS_SRC}/blog-ui.css" "${ASSETS_DST}/blog-ui.css"
cp -f "${ASSETS_SRC}/blog-ui.js" "${ASSETS_DST}/blog-ui.js"
echo "OK: ${MU}/sfrfr-blog-ui.php"
echo "OK: ${ASSETS_DST}/"
