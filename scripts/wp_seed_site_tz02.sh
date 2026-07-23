#!/usr/bin/env bash
# Сид публичного сайта SFRFR по ТЗ docs/specs/02-public-site-wordpress.md (этап 1 roadmap).
# Главная + оферта + ПДн + согласие + CTA MAX + форма лида (без файлов/СНИЛС).
#
# На VPS:
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_site_tz02.sh
#   MAX_PUBLIC_BOT_URL=https://max.ru/... bash scripts/wp_seed_site_tz02.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
MAX_BTN_URL="${MAX_PUBLIC_BOT_URL:-https://max.ru/id8905998693_1_bot?startapp}"
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

OFFER_CONTENT='<!-- wp:paragraph -->
<p><strong>Черновик.</strong> Текст до проверки юристом. Не является окончательной публичной офертой.</p>
<!-- /wp:paragraph -->
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">1. Общие положения</h2>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>1.1. Настоящая оферта регулирует отношения между Исполнителем и Заказчиком (физическим лицом) при заказе услуг диагностики и сопровождения пенсионного дела.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>1.2. Акцепт оферты — оплата услуг и/или подтверждение индивидуального соглашения-заказа в интерфейсе сервиса.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>1.3. Исполнитель не является государственным органом, не заменяет СФР и не гарантирует перерасчёт пенсии или размер выплат.</p>
<!-- /wp:paragraph -->
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">2. Предмет</h2>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>2.1. Диагностика: анализ документов, выявление возможных несоответствий учёта стажа, план действий, индивидуальный чек-лист.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>2.2. Сопровождение: черновики заявлений и запросов, инструкции по самостоятельной подаче через СФР / МФЦ / Госуслуги, консультации и контроль сроков.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>2.3. Подача документов в уполномоченные органы осуществляется исключительно Заказчиком.</p>
<!-- /wp:paragraph -->
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">3. Порядок оказания</h2>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>3.1–3.3. Заказчик предоставляет документы и согласие на обработку ПДн. По каждому делу формируется индивидуальное соглашение-заказ. Воронка ведётся в CRM; чек-лист — в карточке дела.</p>
<!-- /wp:paragraph -->
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">4. Стоимость и оплата</h2>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>4.1. Фиксированная оплата диагностики и сопровождения — по тарифам на сайте / в заказе.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>4.2–4.5. Success fee только при документально подтверждённом повышении пенсии и/или ЕДВ: 10% от ЕДВ и 50% от суммы прибавок за первые три месяца; оплата через 2–3 месяца после результата. Без повышения — success fee не начисляется.</p>
<!-- /wp:paragraph -->
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">5–8. Обязанности, ПДн, ответственность</h2>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>Заказчик предоставляет достоверные документы и сообщает о решении СФР. Обработка ПДн — по согласию и политике. Документы хранятся в защищённом контуре сервиса, не на публичном WordPress. Решение о перерасчёте принимает СФР. Полный текст черновика — у исполнителя / после юридической проверки.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p><a href="/politika-pdn/">Политика обработки ПДн</a> · <a href="/soglasie/">Согласие</a> · <a href="'"${MAX_BTN_URL}"'">Начать проверку в MAX</a></p>
<!-- /wp:paragraph -->'


PRIVACY_CONTENT='<!-- wp:paragraph -->
<p><strong>Черновик</strong> политики обработки персональных данных (SFRFR).</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>Оператор обрабатывает данные обращения (имя, телефон / канал связи) для связи с заявителем и организации услуг диагностики и сопровождения.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>Сканы ИЛС, трудовых книжек, паспортов и СНИЛС не принимаются через сайт WordPress. Такие документы загружаются только в мессенджер MAX или защищённый кабинет.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>Правовые основания — согласие субъекта и договор (оферта / индивидуальный заказ). Срок хранения — в соответствии с целями обработки и требованиями законодательства.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p><a href="/soglasie/">Согласие на обработку</a> · <a href="/oferta/">Оферта</a></p>
<!-- /wp:paragraph -->'

CONSENT_CONTENT='<!-- wp:paragraph -->
<p><strong>Черновик</strong> формы согласия на обработку персональных данных.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>Отправляя заявку на сайте или начиная диалог в MAX, вы подтверждаете согласие на обработку указанных вами данных обращения (имя, телефон / предпочтительный канал связи) в целях обратной связи и оказания услуг SFRFR.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>Вы можете отозвать согласие, направив обращение оператору. Отказ от согласия может сделать невозможным оказание услуги.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>Подробнее: <a href="/politika-pdn/">Политика обработки ПДн</a> · <a href="/oferta/">Оферта</a></p>
<!-- /wp:paragraph -->'

echo "==> Страницы"
HOME_ID="$(upsert_page glavnaya "Главная" "$HOME_FILE")"
rm -f "$HOME_FILE"
OFFER_ID="$(upsert_page oferta "Оферта" "$OFFER_CONTENT")"
PRIVACY_ID="$(upsert_page politika-pdn "Политика обработки ПДн" "$PRIVACY_CONTENT")"
CONSENT_ID="$(upsert_page soglasie "Согласие на обработку ПДн" "$CONSENT_CONTENT")"
echo "HOME=$HOME_ID OFFER=$OFFER_ID PRIVACY=$PRIVACY_ID CONSENT=$CONSENT_ID"

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
  "${WP[@]}" menu item add-post "$MENU_ID" "$HOME_ID" --title="Главная" >/dev/null
  "${WP[@]}" menu item add-post "$MENU_ID" "$OFFER_ID" --title="Оферта" >/dev/null
  "${WP[@]}" menu item add-post "$MENU_ID" "$PRIVACY_ID" --title="Политика ПДн" >/dev/null
  "${WP[@]}" menu item add-post "$MENU_ID" "$CONSENT_ID" --title="Согласие" >/dev/null
  "${WP[@]}" menu item add-custom "$MENU_ID" "Начать проверку" "/#kak-rabotat" >/dev/null
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
  "${WP[@]}" menu item add-custom "$FMENU_ID" "MAX" "$MAX_BTN_URL" >/dev/null
  "${WP[@]}" menu item add-custom "$FMENU_ID" "Кабинет" "${CABINET_URL:-https://cabinet.taxi-doroga-dobra.ru/}" >/dev/null
  "${WP[@]}" menu location assign "$FMENU_ID" footer_menu >/dev/null 2>&1 || true
fi

echo "==> Тема: без сайдбара"
"${WP[@]}" widget reset --all 2>/dev/null || true
"${WP[@]}" theme mod set ast-page-content-layout "page-builder" 2>/dev/null || true
"${WP[@]}" theme mod set site-sidebar-layout "no-sidebar" 2>/dev/null || true

chown -R www-data:www-data "$SITE_DIR"
echo "==> OK ТЗ-02/07: CTA → /#kak-rabotat (выбор канала MAX|кабинет), MAX=${MAX_BTN_URL}"
