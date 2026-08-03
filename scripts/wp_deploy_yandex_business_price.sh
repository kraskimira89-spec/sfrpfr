#!/usr/bin/env bash
# Выложить YML-прайс Яндекс Бизнеса в корень WP-сайта.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SRC="${ROOT}/scripts/assets/yandex-business/price-list.yml"
DST="${SITE_DIR}/yandex-business-price.yml"

if [[ ! -f "${SRC}" ]]; then
  echo "Missing ${SRC}" >&2
  exit 1
fi
cp -f "${SRC}" "${DST}"
chown www-data:www-data "${DST}" 2>/dev/null || true
echo "OK: https://proverkastaza.ru/yandex-business-price.yml"
