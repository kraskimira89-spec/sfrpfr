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
  local slug="$1" title="$2" content="$3"
  local id
  id="$("${WP[@]}" post list --post_type=page --name="$slug" --field=ID 2>/dev/null | head -n1 || true)"
  if [ -z "$id" ]; then
    id="$("${WP[@]}" post create --post_type=page --post_title="$title" --post_name="$slug" \
      --post_status=publish --post_content="$content" --porcelain)"
  else
    "${WP[@]}" post update "$id" --post_title="$title" --post_name="$slug" \
      --post_status=publish --post_content="$content" >/dev/null
  fi
  "${WP[@]}" post meta update "$id" _wp_page_template default 2>/dev/null || true
  echo "$id"
}

echo "==> Тема Astra"
"${WP[@]}" theme install astra --activate --force >/dev/null
"${WP[@]}" plugin activate wpforms-lite 2>/dev/null || true

echo "==> Форма лида WPForms (без файлов и СНИЛС)"
FORM_ID="$("${WP[@]}" eval-file "${SCRIPT_DIR}/wp_ensure_lead_form.php")"
FORM_ID="$(echo "$FORM_ID" | tr -d '[:space:]')"
if [ -z "$FORM_ID" ] || [ "$FORM_ID" = "0" ]; then
  echo "WARN: не удалось создать WPForms; shortcode будет без id"
  FORM_SHORTCODE='<!-- wp:paragraph --><p><em>Форма заявки: включите WPForms Lite и перезапустите сид.</em></p><!-- /wp:paragraph -->'
else
  echo "FORM_ID=$FORM_ID"
  FORM_SHORTCODE="<!-- wp:shortcode -->
[wpforms id=\"${FORM_ID}\" title=\"false\" description=\"true\"]
<!-- /wp:shortcode -->"
fi

HOME_CONTENT="<!-- wp:group {\"align\":\"full\",\"style\":{\"spacing\":{\"padding\":{\"top\":\"5rem\",\"bottom\":\"3rem\",\"left\":\"1.5rem\",\"right\":\"1.5rem\"}}},\"layout\":{\"type\":\"constrained\",\"contentSize\":\"44rem\"}} -->
<div class=\"wp-block-group alignfull\" style=\"padding-top:5rem;padding-right:1.5rem;padding-bottom:3rem;padding-left:1.5rem\">
<!-- wp:heading {\"textAlign\":\"center\",\"level\":1,\"fontSize\":\"xx-large\"} -->
<h1 class=\"wp-block-heading has-text-align-center has-xx-large-font-size\">SFRFR</h1>
<!-- /wp:heading -->
<!-- wp:paragraph {\"align\":\"center\"} -->
<p class=\"has-text-align-center\">Сопровождение пенсионного перерасчёта для частных клиентов: диагностика учёта стажа и подготовка пакета документов.</p>
<!-- /wp:paragraph -->
<!-- wp:buttons {\"layout\":{\"type\":\"flex\",\"justifyContent\":\"center\"}} -->
<div class=\"wp-block-buttons\"><!-- wp:button -->
<div class=\"wp-block-button\"><a class=\"wp-block-button__link wp-element-button\" href=\"${MAX_BTN_URL}\" target=\"_blank\" rel=\"noopener noreferrer\">Начать проверку</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons -->
<!-- wp:paragraph {\"align\":\"center\"} -->
<p class=\"has-text-align-center\"><a href=\"/oferta/\">Оферта</a> · сканы документов — только в MAX / кабинете, не через сайт</p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:group {\"align\":\"full\",\"style\":{\"spacing\":{\"padding\":{\"top\":\"2rem\",\"bottom\":\"2rem\",\"left\":\"1.5rem\",\"right\":\"1.5rem\"}}},\"layout\":{\"type\":\"constrained\",\"contentSize\":\"44rem\"}} -->
<div class=\"wp-block-group alignfull\" style=\"padding-top:2rem;padding-right:1.5rem;padding-bottom:2rem;padding-left:1.5rem\">
<!-- wp:heading {\"level\":2} -->
<h2 class=\"wp-block-heading\">Для кого</h2>
<!-- /wp:heading -->
<!-- wp:paragraph -->
<p>Для тех, кто хочет проверить, правильно ли учтён стаж и нет ли оснований для перерасчёта пенсии — без обещаний «гарантированного повышения».</p>
<!-- /wp:paragraph -->
<!-- wp:heading {\"level\":2} -->
<h2 class=\"wp-block-heading\">Чем помогаем</h2>
<!-- /wp:heading -->
<!-- wp:list -->
<ul class=\"wp-block-list\"><li>Разбираем документы и находим возможные пробелы в учёте.</li><li>Готовим чек-лист и черновики заявлений.</li><li>Даём инструкцию для самостоятельной подачи в СФР / МФЦ / Госуслуги.</li><li>Сопровождаем до понятного результата по делу.</li></ul>
<!-- /wp:list -->
<!-- wp:heading {\"level\":2} -->
<h2 class=\"wp-block-heading\">Как это работает</h2>
<!-- /wp:heading -->
<!-- wp:list {\"ordered\":true} -->
<ol class=\"wp-block-list\"><li>Напишите в MAX или оставьте заявку на сайте.</li><li>Получите согласие и условия работы.</li><li>Передайте документы в защищённый канал (MAX / кабинет).</li><li>Пройдите диагностику и согласуйте план.</li><li>Получите пакет и инструкцию подачи.</li><li>Подайте заявление самостоятельно.</li><li>Сообщите о решении СФР — при подтверждённом результате действует post-payment по оферте.</li></ol>
<!-- /wp:list -->
<!-- wp:paragraph -->
<p><strong>Важно:</strong> не загружайте через сайт сканы ИЛС, трудовой, паспорта или СНИЛС. Для документов используйте чат MAX или кабинет.</p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:group {\"align\":\"full\",\"style\":{\"spacing\":{\"padding\":{\"top\":\"2rem\",\"bottom\":\"4rem\",\"left\":\"1.5rem\",\"right\":\"1.5rem\"}}},\"layout\":{\"type\":\"constrained\",\"contentSize\":\"36rem\"}} -->
<div class=\"wp-block-group alignfull\" style=\"padding-top:2rem;padding-right:1.5rem;padding-bottom:4rem;padding-left:1.5rem\">
<!-- wp:heading {\"textAlign\":\"center\",\"level\":2} -->
<h2 class=\"wp-block-heading has-text-align-center\">Заявка</h2>
<!-- /wp:heading -->
<!-- wp:paragraph {\"align\":\"center\"} -->
<p class=\"has-text-align-center\">Имя, телефон или канал связи и согласие. После отправки мы свяжемся и пришлём ссылку на MAX.</p>
<!-- /wp:paragraph -->
${FORM_SHORTCODE}
<!-- wp:buttons {\"layout\":{\"type\":\"flex\",\"justifyContent\":\"center\"}} -->
<div class=\"wp-block-buttons\"><!-- wp:button {\"className\":\"is-style-outline\"} -->
<div class=\"wp-block-button is-style-outline\"><a class=\"wp-block-button__link wp-element-button\" href=\"${MAX_BTN_URL}\" target=\"_blank\" rel=\"noopener noreferrer\">Или сразу в MAX</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons -->
</div>
<!-- /wp:group -->"

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
HOME_ID="$(upsert_page glavnaya "Главная" "$HOME_CONTENT")"
OFFER_ID="$(upsert_page oferta "Оферта" "$OFFER_CONTENT")"
PRIVACY_ID="$(upsert_page politika-pdn "Политика обработки ПДн" "$PRIVACY_CONTENT")"
CONSENT_ID="$(upsert_page soglasie "Согласие на обработку ПДн" "$CONSENT_CONTENT")"
echo "HOME=$HOME_ID OFFER=$OFFER_ID PRIVACY=$PRIVACY_ID CONSENT=$CONSENT_ID"

"${WP[@]}" option update show_on_front page
"${WP[@]}" option update page_on_front "$HOME_ID"
"${WP[@]}" option update blogdescription "Сопровождение пенсионного перерасчёта"

echo "==> Меню"
MENU_ID="$("${WP[@]}" menu list --fields=term_id,name --format=csv 2>/dev/null | awk -F, '$2=="SFRFR Primary"{print $1; exit}' || true)"
if [ -z "${MENU_ID}" ]; then
  MENU_ID="$("${WP[@]}" menu create "SFRFR Primary" --porcelain)"
fi
# очистить пункты
for item in $("${WP[@]}" menu item list "$MENU_ID" --format=ids 2>/dev/null || true); do
  "${WP[@]}" menu item delete "$item" --force >/dev/null 2>&1 || true
done
"${WP[@]}" menu item add-post "$MENU_ID" "$HOME_ID" --title="Главная" >/dev/null
"${WP[@]}" menu item add-post "$MENU_ID" "$OFFER_ID" --title="Оферта" >/dev/null
"${WP[@]}" menu item add-post "$MENU_ID" "$PRIVACY_ID" --title="Политика ПДн" >/dev/null
"${WP[@]}" menu item add-post "$MENU_ID" "$CONSENT_ID" --title="Согласие" >/dev/null
"${WP[@]}" menu item add-custom "$MENU_ID" "Начать проверку" "$MAX_BTN_URL" >/dev/null
"${WP[@]}" menu location assign "$MENU_ID" primary 2>/dev/null || \
  "${WP[@]}" menu location assign "$MENU_ID" menu-1 2>/dev/null || true

# Футер-меню
FMENU_ID="$("${WP[@]}" menu list --fields=term_id,name --format=csv 2>/dev/null | awk -F, '$2=="SFRFR Footer"{print $1; exit}' || true)"
if [ -z "${FMENU_ID}" ]; then
  FMENU_ID="$("${WP[@]}" menu create "SFRFR Footer" --porcelain)"
fi
for item in $("${WP[@]}" menu item list "$FMENU_ID" --format=ids 2>/dev/null || true); do
  "${WP[@]}" menu item delete "$item" --force >/dev/null 2>&1 || true
done
"${WP[@]}" menu item add-post "$FMENU_ID" "$OFFER_ID" --title="Оферта" >/dev/null
"${WP[@]}" menu item add-post "$FMENU_ID" "$PRIVACY_ID" --title="Политика ПДн" >/dev/null
"${WP[@]}" menu item add-post "$FMENU_ID" "$CONSENT_ID" --title="Согласие" >/dev/null
"${WP[@]}" menu item add-custom "$FMENU_ID" "MAX" "$MAX_BTN_URL" >/dev/null
"${WP[@]}" menu location assign "$FMENU_ID" footer_menu 2>/dev/null || \
  "${WP[@]}" menu location assign "$FMENU_ID" footer 2>/dev/null || true

echo "==> Тема: без сайдбара"
"${WP[@]}" widget reset --all 2>/dev/null || true
"${WP[@]}" theme mod set ast-page-content-layout "page-builder" 2>/dev/null || true
"${WP[@]}" theme mod set site-sidebar-layout "no-sidebar" 2>/dev/null || true

chown -R www-data:www-data "$SITE_DIR"
echo "==> OK ТЗ-02: https://taxi-doroga-dobra.ru/ (CTA MAX=${MAX_BTN_URL})"
