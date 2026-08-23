#!/usr/bin/env bash
# Выложить PDF лид-магнита A4 в корень WP-сайта (рассылка / прямая ссылка).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SRC="${ROOT}/scripts/assets/leadmagnets/pension-checklist-a4-standard.pdf"
DST="${SITE_DIR}/pension-checklist-a4.pdf"
SRC_BW="${ROOT}/scripts/assets/leadmagnets/pension-checklist-a4-bw.pdf"
DST_BW="${SITE_DIR}/pension-checklist-a4-bw.pdf"

if [[ ! -f "$SRC" ]]; then
  echo "WARN: missing $SRC — запустите python scripts/build_leadmagnet_a4_pdf.py"
  exit 0
fi
install -m 644 "$SRC" "$DST"
echo "OK: https://proverkastaza.ru/pension-checklist-a4.pdf"
if [[ -f "$SRC_BW" ]]; then
  install -m 644 "$SRC_BW" "$DST_BW"
  echo "OK: https://proverkastaza.ru/pension-checklist-a4-bw.pdf"
fi
