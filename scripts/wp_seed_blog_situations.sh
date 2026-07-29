#!/usr/bin/env bash
# LEGACY: массовый сид situations/analitika.
#
# Политика SFRFR (с 2026-07-29):
# - запрещён по умолчанию;
# - статьи и примеры дальше правятся только вручную;
# - ИИ даёт рекомендации, не пересиживает контент.
#
# Аварийный обход:
#   SFRFR_ALLOW_SITUATIONS_SEED=1 SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_blog_situations.sh

set -euo pipefail

if [[ "${SFRFR_ALLOW_SITUATIONS_SEED:-}" != "1" ]]; then
  echo "REFUSED: wp_seed_blog_situations.sh запрещён политикой контента." >&2
  echo "Дальше: только ручное редактирование HTML/постов. ИИ — рекомендации." >&2
  echo "Аварийный обход: SFRFR_ALLOW_SITUATIONS_SEED=1" >&2
  exit 2
fi

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

# Генерацию HTML тоже не запускаем молча — только с отдельным флагом.
if [[ "${SFRFR_ALLOW_SITUATIONS_GENERATE:-}" == "1" ]]; then
  echo "==> Генерация HTML (явный флаг SFRFR_ALLOW_SITUATIONS_GENERATE=1)"
  (cd "${SCRIPT_DIR}/.." && SFRFR_ALLOW_SITUATIONS_GENERATE=1 python3 scripts/generate_blog_situations.py)
else
  echo "==> Генерация HTML пропущена (используем существующие файлы в git)"
fi

export SFRFR_SITUATIONS_HTML="${SCRIPT_DIR}/assets/blog/situations/html"
if [[ ! -f "${SFRFR_SITUATIONS_HTML}/index.json" ]]; then
  echo "ERROR: нет index.json в git/assets. Ручная правка или аварийный generate." >&2
  exit 1
fi

export SFRFR_ALLOW_SITUATIONS_SEED=1
echo "==> Сид ситуаций и аналитики (аварийный)"
"${WP[@]}" eval-file "${SCRIPT_DIR}/wp_seed_blog_situations.php"

echo "==> OK: /blog/rubrika/situacii/ + /blog/rubrika/analitika/"
