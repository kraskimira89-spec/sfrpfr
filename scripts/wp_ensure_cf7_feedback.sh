#!/usr/bin/env bash
# Contact Form 7 + Flamingo + форма «Обратная связь».
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_ensure_cf7_feedback.sh
set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

ensure_plugin() {
  local slug="$1"
  if "${WP[@]}" plugin is-installed "$slug" >/dev/null 2>&1; then
    "${WP[@]}" plugin activate "$slug" >/dev/null 2>&1 || true
  else
    echo "==> Install plugin ${slug}"
    "${WP[@]}" plugin install "$slug" --activate
  fi
}

echo "==> Contact Form 7 + Flamingo"
ensure_plugin contact-form-7
ensure_plugin flamingo

lang="$("${WP[@]}" option get WPLANG 2>/dev/null || true)"
if [[ "${lang}" == ru_RU ]]; then
  "${WP[@]}" language plugin install contact-form-7 ru_RU 2>/dev/null || true
  "${WP[@]}" language plugin install flamingo ru_RU 2>/dev/null || true
fi

MU="${SITE_DIR}/wp-content/mu-plugins"
mkdir -p "${MU}"
cp -f "${SCRIPT_DIR}/wp-mu-plugins/sfrfr-cf7-feedback.php" "${MU}/sfrfr-cf7-feedback.php"
chown www-data:www-data "${MU}/sfrfr-cf7-feedback.php" 2>/dev/null || true

echo "==> Ensure CF7 feedback form"
form_id="$("${WP[@]}" eval-file "${SCRIPT_DIR}/wp_ensure_cf7_feedback.php" | tr -d '[:space:]' || true)"
if [[ -z "${form_id}" || "${form_id}" == "0" ]]; then
  echo "WARN: CF7 form ensure failed"
  exit 0
fi
echo "CF7_FEEDBACK_ID=${form_id}"
"${WP[@]}" cache flush >/dev/null 2>&1 || true
