#!/usr/bin/env bash
# ТЗ-11: изолированный backup + публикация только блога.
#
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_blog_tz11.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

export SFRFR_BLOG_ASSETS="${SCRIPT_DIR}/assets/blog"

BACKUP_ROOT="${SFRFR_BLOG_BACKUP_ROOT:-/root/.sfrfr-backups/blog}"
BACKUP_DIR="${BACKUP_ROOT}/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
echo "==> Backup текущих записей: ${BACKUP_DIR}"
# WP-CLI sprintf: литеральный % в имени файла нужно экранировать как %%
if ! "${WP[@]}" export \
  --post_type=post \
  --dir="$BACKUP_DIR" \
  --filename_format='blog-before-seed-%%Y-%%m-%%d.xml'; then
  echo "WARN: wp export backup failed — продолжаем сид без бэкапа"
fi

# Лендинг и его CSS по умолчанию не трогаем. Включать только явно.
if [[ "${SFRFR_BLOG_APPLY_CSS:-0}" == "1" ]]; then
  echo "==> CSS (явно включён SFRFR_BLOG_APPLY_CSS=1)"
  export SFRFR_CSS_PATH="${SCRIPT_DIR}/assets/sfrfr-landing.css"
  "${WP[@]}" eval-file "${SCRIPT_DIR}/wp_apply_landing_css.php"
fi

echo "==> Сид блога ТЗ-11"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_seed_blog_tz11.php"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_apply_author_display.php" || true

echo "==> OK ТЗ-11: /blog/ + статьи (вкл. контент с главной), CTA → /#kak-rabotat"
