#!/usr/bin/env bash
# Один проход SEO-консолидации на VPS (после git pull).
#   bash scripts/wp_deploy_seo_consolidation.sh
set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

echo "==> MU + blog UI"
bash "${SCRIPT_DIR}/wp_deploy_blog_ui.sh"

echo "==> Seed pillars TZ-11"
export SFRFR_BLOG_ASSETS="${SCRIPT_DIR}/assets/blog"
bash "${SCRIPT_DIR}/wp_seed_blog_tz11.sh"

echo "==> Situations/analitika: без автопересида (политика: только ручное редактирование)"

echo "==> Mark thin noindex"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_mark_thin_blog_noindex.php"

echo "==> Repair SEO descriptions"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_repair_seo_descriptions.php"

"${WP[@]}" cache flush || true
"${WP[@]}" super-cache flush 2>/dev/null || true

echo "==> OK SEO consolidation at ${ROOT}"
