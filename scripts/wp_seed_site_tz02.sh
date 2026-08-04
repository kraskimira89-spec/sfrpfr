#!/usr/bin/env bash
# Сид публичного сайта SFRFR по ТЗ docs/specs/02-public-site-wordpress.md (этап 1 roadmap).
# Главная + оферта + ПДн + согласие + CTA MAX + форма лида (без файлов/СНИЛС).
#
# На VPS:
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_site_tz02.sh
#   MAX_PUBLIC_BOT_URL=https://max.ru/... bash scripts/wp_seed_site_tz02.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
MAX_BTN_URL="${MAX_CHAT_URL:-${MAX_PUBLIC_BOT_URL:-https://max.ru/id8905998693_1_bot}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WP=(wp --path="$SITE_DIR" --allow-root)

upsert_page() {
  local slug="$1" title="$2" content_or_file="$3"
  local id content
  if [ -f "$content_or_file" ]; then
    content="$(cat "$content_or_file")"
  else
    content="$content_or_file"
  fi
  id="$("${WP[@]}" post list --post_type=page --name="$slug" --field=ID 2>/dev/null | head -n1 | tr -d '[:space:]' || true)"
  if [ -z "$id" ]; then
    id="$("${WP[@]}" post create --post_type=page --post_title="$title" --post_name="$slug" \
      --post_status=publish --porcelain 2>/dev/null | tr -d '[:space:]')"
  fi
  # контент через PHP — надёжнее для большого HTML
  CONTENT_FILE="$(mktemp)"
  printf '%s' "$content" >"$CONTENT_FILE"
  "${WP[@]}" eval "
\$id = ${id};
\$c = file_get_contents('${CONTENT_FILE}');
wp_update_post(['ID' => \$id, 'post_title' => '${title}', 'post_name' => '${slug}', 'post_status' => 'publish', 'post_content' => \$c]);
" >/dev/null
  rm -f "$CONTENT_FILE"
  "${WP[@]}" post meta update "$id" _wp_page_template default >/dev/null 2>&1 || true
  echo "$id" | grep -Eo '^[0-9]+$' | head -n1
}


echo "==> Тема Astra"
"${WP[@]}" theme install astra --activate --force >/dev/null
"${WP[@]}" plugin activate wpforms-lite 2>/dev/null || true

echo "==> MU-plugin: reCAPTCHA Enterprise + lead API + Yandex verification"
mkdir -p "${SITE_DIR}/wp-content/mu-plugins"
cp -f "${SCRIPT_DIR}/wp-mu-plugins/sfrfr-recaptcha-lead.php" "${SITE_DIR}/wp-content/mu-plugins/sfrfr-recaptcha-lead.php"
cp -f "${SCRIPT_DIR}/assets/sfrfr-recaptcha-lead.js" "${SITE_DIR}/wp-content/mu-plugins/sfrfr-recaptcha-lead.js"
cp -f "${SCRIPT_DIR}/wp-mu-plugins/sfrfr-yandex-verification.php" "${SITE_DIR}/wp-content/mu-plugins/sfrfr-yandex-verification.php"
mkdir -p "${SITE_DIR}/wp-content/uploads/sfrfr"
cp -f "${SCRIPT_DIR}/assets/sfrfr-recaptcha-lead.js" "${SITE_DIR}/wp-content/uploads/sfrfr/sfrfr-recaptcha-lead.js"
chown -R www-data:www-data "${SITE_DIR}/wp-content/mu-plugins" "${SITE_DIR}/wp-content/uploads/sfrfr" 2>/dev/null || true

echo "==> Форма лида WPForms (без файлов и СНИЛС)"
FORM_ID="$("${WP[@]}" eval-file "${SCRIPT_DIR}/wp_ensure_lead_form.php")"
FORM_ID="$(echo "$FORM_ID" | tr -d '[:space:]')"
FORM_FILE="$(mktemp)"
if [ -z "$FORM_ID" ] || [ "$FORM_ID" = "0" ]; then
  echo "WARN: не удалось создать WPForms; shortcode будет без id"
  printf '%s\n' '<!-- wp:paragraph --><p><em>Форма заявки: включите WPForms Lite и перезапустите сид.</em></p><!-- /wp:paragraph -->' >"$FORM_FILE"
else
  echo "FORM_ID=$FORM_ID"
  printf '%s\n' "<!-- wp:shortcode -->" "[wpforms id=\"${FORM_ID}\" title=\"false\" description=\"true\"]" "<!-- /wp:shortcode -->" >"$FORM_FILE"
fi

echo "==> CSS лендинга"
export SFRFR_CSS_PATH="${SCRIPT_DIR}/assets/sfrfr-landing.css"
CSS_ID="$("${WP[@]}" eval-file "${SCRIPT_DIR}/wp_apply_landing_css.php" 2>/dev/null | tr -d '[:space:]' || true)"
echo "CUSTOM_CSS_POST=${CSS_ID:-?}"

echo "==> Логотип и favicon (светлый фон)"
mkdir -p "${SITE_DIR}/wp-content/uploads/sfrfr"
cp -f "${SCRIPT_DIR}/assets/sfrfr-logo-light.png" "${SITE_DIR}/wp-content/uploads/sfrfr/sfrfr-logo-light.png"
chown -R www-data:www-data "${SITE_DIR}/wp-content/uploads/sfrfr" 2>/dev/null || true
export SFRFR_LOGO_LIGHT="${SCRIPT_DIR}/assets/sfrfr-logo-light.png"
LOGO_ID="$("${WP[@]}" eval-file "${SCRIPT_DIR}/wp_apply_branding.php" 2>/dev/null | tr -d '[:space:]' || true)"
echo "LOGO_ID=${LOGO_ID:-?}"

echo "==> Контент главной (концепция SFRFR)"
HOME_FILE="$(mktemp)"
HOME_SRC="${SCRIPT_DIR}/assets/sfrfr-home.html"
python3 - "$HOME_SRC" "$HOME_FILE" "$MAX_BTN_URL" "$FORM_FILE" <<'PY'
import sys
src, dst, max_url, form_path = sys.argv[1:5]
text = open(src, encoding="utf-8").read().replace("{{MAX_BTN_URL}}", max_url)
form_block = open(form_path, encoding="utf-8").read().strip()
marker = "<!-- SFRFR_FORM -->"
if marker not in text:
    raise SystemExit("SFRFR_FORM marker missing")
before, after = text.split(marker, 1)
out = before.rstrip() + "\n<!-- /wp:html -->\n" + form_block + "\n<!-- wp:html -->\n" + after.lstrip()
open(dst, "w", encoding="utf-8").write(out)
PY
rm -f "$FORM_FILE"

OFFER_FILE="${SCRIPT_DIR}/assets/sfrfr-oferta.html"
if [ ! -f "$OFFER_FILE" ]; then
  echo "ERROR: файл оферты не найден: $OFFER_FILE" >&2
  exit 1
fi


PRIVACY_FILE="${SCRIPT_DIR}/assets/sfrfr-privacy.html"
if [ ! -f "$PRIVACY_FILE" ]; then
  echo "ERROR: файл политики ПДн не найден: $PRIVACY_FILE" >&2
  exit 1
fi

CONSENT_FILE="${SCRIPT_DIR}/assets/sfrfr-consent.html"
if [ ! -f "$CONSENT_FILE" ]; then
  echo "ERROR: файл согласия не найден: $CONSENT_FILE" >&2
  exit 1
fi

echo "==> Страницы"
HOME_ID="$(upsert_page glavnaya "Главная" "$HOME_FILE")"
rm -f "$HOME_FILE"
OFFER_ID="$(upsert_page oferta "Публичная оферта" "$OFFER_FILE")"
PRIVACY_ID="$(upsert_page politika-pdn "Политика обработки персональных данных" "$PRIVACY_FILE")"
CONSENT_ID="$(upsert_page soglasie "Согласие на обработку персональных данных" "$CONSENT_FILE")"
COOKIES_FILE="${SCRIPT_DIR}/assets/sfrfr-cookies.html"
COOKIES_ID=""
if [ -f "$COOKIES_FILE" ]; then
  COOKIES_ID="$(upsert_page cookies "Правила использования файлов браузера" "$COOKIES_FILE")"
fi
echo "HOME=$HOME_ID OFFER=$OFFER_ID PRIVACY=$PRIVACY_ID CONSENT=$CONSENT_ID COOKIES=$COOKIES_ID"

"${WP[@]}" option update show_on_front page
"${WP[@]}" option update page_on_front "$HOME_ID"
"${WP[@]}" option update blogname "Проверка стажа"
"${WP[@]}" option update blogdescription "Сопровождение пенсионного перерасчёта"

echo "==> Меню"
clear_menu_items() {
  local mid="$1"
  "${WP[@]}" eval "
\$items = wp_get_nav_menu_items(${mid}, ['post_status' => 'any']);
if (\$items) {
  foreach (\$items as \$item) {
    wp_delete_post(\$item->ID, true);
  }
}
" >/dev/null 2>&1 || true
}

find_or_create_menu() {
  local name="$1"
  local id
  id="$("${WP[@]}" menu list --format=json 2>/dev/null | php -r '
$want = $argv[1];
$j = json_decode(stream_get_contents(STDIN), true);
foreach ((array)$j as $m) {
  if (($m["name"] ?? "") === $want) { echo (int)$m["term_id"]; exit; }
}
' "$name" || true)"
  if [ -z "$id" ]; then
    id="$("${WP[@]}" menu create "$name" --porcelain 2>/dev/null || true)"
  fi
  if [ -z "$id" ]; then
    id="$("${WP[@]}" menu list --format=json 2>/dev/null | php -r '
$want = $argv[1];
$j = json_decode(stream_get_contents(STDIN), true);
foreach ((array)$j as $m) {
  if (($m["name"] ?? "") === $want) { echo (int)$m["term_id"]; exit; }
}
' "$name" || true)"
  fi
  echo "$id"
}

MENU_ID="$(find_or_create_menu "SFRFR Primary")"
echo "MENU_ID=${MENU_ID}"
if [ -n "${MENU_ID}" ]; then
  clear_menu_items "$MENU_ID"
  # Короткая воронка: оферта/ПДн — только в footer
  "${WP[@]}" menu item add-post "$MENU_ID" "$HOME_ID" --title="Главная" >/dev/null
  "${WP[@]}" menu item add-custom "$MENU_ID" "Как это работает" "/#kak-prohodit" >/dev/null
  "${WP[@]}" menu item add-custom "$MENU_ID" "Тарифы" "/#tarify" >/dev/null
  "${WP[@]}" menu item add-custom "$MENU_ID" "Вопросы" "/#faq" >/dev/null
  "${WP[@]}" menu item add-custom "$MENU_ID" "О сервисе" "/#o-servise" >/dev/null
  "${WP[@]}" menu item add-custom "$MENU_ID" "Статьи" "/blog/" >/dev/null
  CTA_ITEM="$("${WP[@]}" menu item add-custom "$MENU_ID" "Начать проверку в MAX" "$MAX_BTN_URL" --porcelain 2>/dev/null | tr -d '[:space:]')"
  if [ -n "${CTA_ITEM:-}" ]; then
    "${WP[@]}" post term set "$CTA_ITEM" nav_menu "$MENU_ID" >/dev/null 2>&1 || true
    "${WP[@]}" post meta update "$CTA_ITEM" _menu_item_classes "sfrfr-menu-cta" >/dev/null 2>&1 || true
  fi
  "${WP[@]}" menu location assign "$MENU_ID" primary >/dev/null 2>&1 || true
  "${WP[@]}" menu location unset secondary_menu >/dev/null 2>&1 || true
fi

FMENU_ID="$(find_or_create_menu "SFRFR Footer")"
echo "FMENU_ID=${FMENU_ID}"
if [ -n "${FMENU_ID}" ]; then
  clear_menu_items "$FMENU_ID"
  "${WP[@]}" menu item add-post "$FMENU_ID" "$OFFER_ID" --title="Оферта" >/dev/null
  "${WP[@]}" menu item add-post "$FMENU_ID" "$PRIVACY_ID" --title="Политика ПДн" >/dev/null
  "${WP[@]}" menu item add-post "$FMENU_ID" "$CONSENT_ID" --title="Согласие" >/dev/null
  "${WP[@]}" menu item add-custom "$FMENU_ID" "Статьи" "/blog/" >/dev/null
  "${WP[@]}" menu item add-custom "$FMENU_ID" "MAX" "$MAX_BTN_URL" >/dev/null
  "${WP[@]}" menu item add-custom "$FMENU_ID" "Личный кабинет" "${CABINET_URL:-https://cabinet.proverkastaza.ru}/" >/dev/null
  "${WP[@]}" menu location assign "$FMENU_ID" footer_menu >/dev/null 2>&1 || true
fi

echo "==> Тема: без сайдбара"
"${WP[@]}" widget reset --all 2>/dev/null || true
"${WP[@]}" theme mod set ast-page-content-layout "page-builder" 2>/dev/null || true
"${WP[@]}" theme mod set site-sidebar-layout "no-sidebar" 2>/dev/null || true

chown -R www-data:www-data "$SITE_DIR"
echo "==> OK ТЗ-02/07/20: CTA → личный чат MAX (${MAX_BTN_URL}), кабинет в футере"

if [ -x "${SCRIPT_DIR}/wp_seed_blog_tz11.sh" ] || [ -f "${SCRIPT_DIR}/wp_seed_blog_tz11.sh" ]; then
  echo "==> Блог ТЗ-11"
  bash "${SCRIPT_DIR}/wp_seed_blog_tz11.sh" || echo "WARN: blog seed failed"
fi

if [ -f "${SCRIPT_DIR}/wp_seed_blog_situations.sh" ]; then
  if [ "${SFRFR_ALLOW_SITUATIONS_SEED:-}" = "1" ]; then
    echo "==> Блог: ситуации/аналитика (явный аварийный флаг)"
    bash "${SCRIPT_DIR}/wp_seed_blog_situations.sh" || echo "WARN: situations seed failed"
  else
    echo "==> Блог: situations/analitika пропущены (политика: только ручное редактирование)"
  fi
fi

# P1 Вебмастер: переобход ключевых URL после сида (нужен secrets/yandex-webmaster.env)
SECRETS_WM="${SCRIPT_DIR}/../secrets/yandex-webmaster.env"
if [ "${SFRFR_WEBMASTER_RECRAWL:-1}" = "1" ] && [ -f "${SCRIPT_DIR}/yandex_webmaster_recrawl.py" ] && [ -f "$SECRETS_WM" ]; then
  echo "==> Яндекс Вебмастер: recrawl"
  if command -v python3 >/dev/null 2>&1; then
    python3 "${SCRIPT_DIR}/yandex_webmaster_recrawl.py" || echo "WARN: webmaster recrawl failed"
  elif command -v python >/dev/null 2>&1; then
    python "${SCRIPT_DIR}/yandex_webmaster_recrawl.py" || echo "WARN: webmaster recrawl failed"
  fi
fi
