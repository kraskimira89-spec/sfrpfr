#!/usr/bin/env bash
# Выложить QR отзыва Яндекс Бизнеса в корень WP-сайта.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SRC="${ROOT}/scripts/assets/yandex-business/promo/qr-review.png"
DST="${SITE_DIR}/yandex-review-qr.png"

if [[ ! -f "$SRC" ]]; then
  echo "WARN: missing $SRC"
  exit 0
fi
install -m 644 "$SRC" "$DST"
echo "OK: https://proverkastaza.ru/yandex-review-qr.png"
