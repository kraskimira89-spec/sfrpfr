#!/usr/bin/env bash
# Обезличенные ситуации DeepSeek + аналитика каждые 5 клиентов.
#
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_blog_situations.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

echo "==> Генерация HTML (если есть python3)"
if command -v python3 >/dev/null 2>&1; then
  (cd "${SCRIPT_DIR}/.." && python3 scripts/generate_blog_situations.py) || true
fi

export SFRFR_SITUATIONS_HTML="${SCRIPT_DIR}/assets/blog/situations/html"
if [[ ! -f "${SFRFR_SITUATIONS_HTML}/index.json" ]]; then
  echo "ERROR: нет index.json — сначала локально: python scripts/generate_blog_situations.py" >&2
  exit 1
fi

echo "==> Сид ситуаций и аналитики"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_seed_blog_situations.php"

echo "==> OK: /blog/rubrika/situacii/ + /blog/rubrika/analitika/"
