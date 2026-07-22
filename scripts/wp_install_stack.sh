#!/usr/bin/env bash
# Стек витрины SFRFR (WordPress). Скрипт в репозитории GitHub; установка через WP-CLI (wordpress.org).
#
# Выбор для старта:
#   тема: Astra (лёгкая)
#   конструктор: Spectra (один; Elementor не ставим)
#   кэш: WP Super Cache (Apache на VPS; не LiteSpeed Cache)
#   Really Simple SSL: НЕ ставим — SSL уже через certbot/Apache
#
# На VPS:
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_install_stack.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
WP=(wp --path="$SITE_DIR" --allow-root)

echo "==> Тема Astra"
"${WP[@]}" theme install astra --activate --force

echo "==> Плагины"
# Spectra = Ultimate Addons for Gutenberg (slug: ultimate-addons-for-gutenberg)
"${WP[@]}" plugin install \
  ultimate-addons-for-gutenberg \
  wpforms-lite \
  seo-by-rank-math \
  updraftplus \
  wordfence \
  wp-super-cache \
  --activate \
  --force

echo "==> Не ставим: elementor, generatepress, litespeed-cache, really-simple-ssl"

# На всякий случай выключить тяжёлые/дубли, если уже были
for p in elementor litespeed-cache really-simple-ssl; do
  if "${WP[@]}" plugin is-installed "$p" 2>/dev/null; then
    "${WP[@]}" plugin deactivate "$p" 2>/dev/null || true
  fi
done

# WP Super Cache: включить простой режим кэша
"${WP[@]}" plugin activate wp-super-cache 2>/dev/null || true
"${WP[@]}" super-cache enable 2>/dev/null || true

chown -R www-data:www-data "$SITE_DIR"
echo "==> OK: стек установлен (Astra + Spectra + WPForms Lite + Rank Math + UpdraftPlus + Wordfence + WP Super Cache)"
"${WP[@]}" theme list --status=active
"${WP[@]}" plugin list --status=active --fields=name,status,version
