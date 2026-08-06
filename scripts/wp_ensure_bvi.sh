#!/usr/bin/env bash
# Установить/включить BVI (версия для слабовидящих) на WordPress.
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_ensure_bvi.sh
set -euo pipefail
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

if ! "${WP[@]}" plugin is-installed button-visually-impaired; then
  echo "==> Install button-visually-impaired"
  "${WP[@]}" plugin install button-visually-impaired --activate
else
  echo "==> Activate button-visually-impaired"
  "${WP[@]}" plugin activate button-visually-impaired || true
fi

"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_ensure_bvi.php"
echo "==> OK BVI"
