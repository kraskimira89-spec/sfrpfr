#!/usr/bin/env bash
# ТЗ-11: блог — рубрики, /blog/, 4 статьи P0, меню «Статьи».
#
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_blog_tz11.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

export SFRFR_BLOG_ASSETS="${SCRIPT_DIR}/assets/blog"

echo "==> CSS (включая стили блога)"
export SFRFR_CSS_PATH="${SCRIPT_DIR}/assets/sfrfr-landing.css"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_apply_landing_css.php" >/dev/null || true

echo "==> Сид блога ТЗ-11"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_seed_blog_tz11.php"

echo "==> OK ТЗ-11: /blog/ + статьи (вкл. контент с главной), CTA → /#kak-rabotat"
