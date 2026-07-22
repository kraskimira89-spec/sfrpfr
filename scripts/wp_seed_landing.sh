#!/usr/bin/env bash
# Сид посадочной SFRFR на WordPress (Zakra + блоки).
# Использование на VPS:
#   bash scripts/wp_seed_landing.sh
#   SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_landing.sh

set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
WP=(wp --path="$SITE_DIR" --allow-root)

echo "==> Тема Zakra"
"${WP[@]}" theme install zakra --activate --force

# Контент главной: бренд + подзаголовок + CTA-заглушка MAX
# MAX_PUBLIC_BOT_URL подставить позже (сейчас href="#")
CONTENT='<!-- wp:group {"align":"full","style":{"spacing":{"padding":{"top":"6rem","bottom":"6rem","left":"1.5rem","right":"1.5rem"}}},"layout":{"type":"constrained","contentSize":"42rem"}} -->
<div class="wp-block-group alignfull" style="padding-top:6rem;padding-right:1.5rem;padding-bottom:6rem;padding-left:1.5rem">
<!-- wp:heading {"textAlign":"center","level":1,"fontSize":"xx-large"} -->
<h1 class="wp-block-heading has-text-align-center has-xx-large-font-size">SFRFR</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {"align":"center"} -->
<p class="has-text-align-center">Сопровождение пенсионного перерасчёта — диагностика и подготовка пакета документов.</p>
<!-- /wp:paragraph -->

<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"}} -->
<div class="wp-block-buttons">
<!-- wp:button -->
<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="#" aria-disabled="true">Написать в MAX (скоро)</a></div>
<!-- /wp:button -->
</div>
<!-- /wp:buttons -->
</div>
<!-- /wp:group -->'

echo "==> Страница Главная"
PAGE_ID="$("${WP[@]}" post list --post_type=page --name=glavnaya --field=ID 2>/dev/null || true)"
if [ -z "${PAGE_ID}" ]; then
  PAGE_ID="$("${WP[@]}" post list --post_type=page --title=Главная --field=ID 2>/dev/null | head -n1 || true)"
fi

if [ -n "${PAGE_ID}" ]; then
  "${WP[@]}" post update "$PAGE_ID" --post_title="Главная" --post_name=glavnaya --post_status=publish --post_content="$CONTENT"
else
  PAGE_ID="$("${WP[@]}" post create --post_type=page --post_title="Главная" --post_name=glavnaya --post_status=publish --post_content="$CONTENT" --porcelain)"
fi

echo "PAGE_ID=$PAGE_ID"
"${WP[@]}" option update show_on_front page
"${WP[@]}" option update page_on_front "$PAGE_ID"
"${WP[@]}" option update blogdescription "Сопровождение пенсионного перерасчёта"

# Убрать шумные виджеты (сайдбар / футер)
echo "==> Очистка виджетов"
"${WP[@]}" widget reset --all 2>/dev/null || true

# Шаблон страницы без сайдбара, если Zakra поддерживает
"${WP[@]}" post meta update "$PAGE_ID" _wp_page_template default 2>/dev/null || true

# Zakra: отключить сайдбар на главной через тему-моды (безопасно, если ключ есть)
"${WP[@]}" theme mod set zakra_page_sidebar_layout "no_sidebar" 2>/dev/null || true
"${WP[@]}" theme mod set zakra_blog_sidebar_layout "no_sidebar" 2>/dev/null || true

chown -R www-data:www-data "$SITE_DIR"
echo "==> OK: https://taxi-doroga-dobra.ru/"
