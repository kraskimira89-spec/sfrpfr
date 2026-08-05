<?php
/**
 * Plugin Name: SFRFR Blog UI (ТЗ-11 §13)
 * Description: Чипы рубрик, TOC, CTA mid/end на блоге.
 * MU-plugin: copy to wp-content/mu-plugins/ (or symlink from /opt/sfrfr/scripts/wp-mu-plugins/).
 */

if (!defined('ABSPATH')) {
    exit;
}

/** ТЗ-11 §8: комментарии к постам выключены (спам + риск ПДн). */
add_filter('comments_open', static function ($open, $post_id) {
    $post = get_post($post_id);
    if ($post && $post->post_type === 'post') {
        return false;
    }
    return $open;
}, 20, 2);
add_filter('pings_open', static function ($open, $post_id) {
    $post = get_post($post_id);
    if ($post && $post->post_type === 'post') {
        return false;
    }
    return $open;
}, 20, 2);
add_filter('comments_template', static function ($template) {
    if (is_singular('post')) {
        return __DIR__ . '/sfrfr-blog-ui-empty-comments.php';
    }
    return $template;
});

/**
 * Публичный URL личного чата MAX для CTA «Уточнить ситуацию в MAX».
 */
function sfrfr_blog_max_chat_url(): string
{
    $url = getenv('MAX_CHAT_URL') ?: getenv('MAX_PUBLIC_BOT_URL') ?: '';
    $url = is_string($url) ? trim($url) : '';
    if ($url === '') {
        $url = (string) get_option('sfrfr_max_chat_url', '');
    }
    if ($url === '') {
        $url = 'https://max.ru/id8905998693_1_bot';
    }
    // ТЗ-20/21: CTA — личный чат, не mini-app
    $url = preg_replace('/\?startapp.*$/i', '', $url) ?: $url;
    return $url !== '' ? $url : 'https://max.ru/id8905998693_1_bot';
}

/**
 * Кнопки CTA: MAX + форма лида.
 */
function sfrfr_blog_ask_cta_buttons_html(): string
{
    $max = esc_url(sfrfr_blog_max_chat_url());
    $form = esc_url(home_url('/#zayavka'));
    return '<a class="sfrfr-blog-cta__btn" href="' . $max . '" target="_blank" rel="noopener noreferrer">Уточнить ситуацию в MAX</a>'
        . ' <a class="sfrfr-blog-cta__btn sfrfr-blog-cta__btn--ghost" href="' . $form . '">Оставить заявку</a>';
}

/**
 * @return array<string, string> slug => label
 */
function sfrfr_blog_ui_chip_map(): array
{
    return [
        '' => 'Все',
        'ils' => 'ИЛС',
        'stazh' => 'Стаж',
        'dokumenty' => 'Документы',
        'podacha' => 'Подача',
        'rodstvenniki' => 'Родственникам',
        'usluga' => 'Услуга',
        'situacii' => 'Ситуации',
        'analitika' => 'Аналитика',
    ];
}

function sfrfr_blog_ui_asset_base(): string
{
    $env = getenv('SFRFR_BLOG_UI_URL');
    if (is_string($env) && $env !== '') {
        return rtrim($env, '/');
    }
    // Default: assets deployed next to mu-plugin under /opt/sfrfr
    return content_url('mu-plugins/sfrfr-blog-ui-assets');
}

function sfrfr_blog_ui_should_load(): bool
{
    return is_home() || is_category() || is_singular('post');
}

add_action('wp_enqueue_scripts', static function (): void {
    if (!sfrfr_blog_ui_should_load()) {
        return;
    }
    $base = sfrfr_blog_ui_asset_base();
    $ver = '20260805a';
    wp_enqueue_style('sfrfr-blog-ui', $base . '/blog-ui.css', [], $ver);
    if (is_singular('post')) {
        wp_enqueue_script('sfrfr-blog-ui', $base . '/blog-ui.js', [], $ver, true);
        wp_localize_script('sfrfr-blog-ui', 'sfrfrBlogUi', [
            'maxUrl' => sfrfr_blog_max_chat_url(),
            'formUrl' => home_url('/#zayavka'),
            'startUrl' => sfrfr_blog_max_chat_url(),
        ]);
    }
});

add_filter('body_class', static function (array $classes): array {
    if (is_singular('post')) {
        $classes[] = 'sfrfr-blog-single';
    }
    if (is_home() || is_category()) {
        $classes[] = 'sfrfr-blog-archive';
    }
    return $classes;
});

/**
 * Chips + archive CTA above the loop on blog index / categories.
 */
add_action('loop_start', static function ($query): void {
    if (is_admin() || !$query instanceof WP_Query || !$query->is_main_query()) {
        return;
    }
    if (!is_home() && !is_category()) {
        return;
    }

    $chips = sfrfr_blog_ui_chip_map();
    $current = '';
    if (is_category()) {
        $obj = get_queried_object();
        if ($obj instanceof WP_Term) {
            $current = $obj->slug;
        }
    }

    if (is_home()) {
        echo '<h1 class="sfrfr-blog-archive__title">Статьи о проверке стажа и ИЛС</h1>';
    }

    echo '<ul class="sfrfr-blog-chips" aria-label="Рубрики блога">';
    foreach ($chips as $slug => $label) {
        $url = $slug === '' ? home_url('/blog/') : home_url('/blog/rubrika/' . rawurlencode($slug) . '/');
        $active = ($slug === $current) || ($slug === '' && is_home());
        printf(
            '<li><a class="%s" href="%s">%s</a></li>',
            $active ? 'is-active' : '',
            esc_url($url),
            esc_html($label)
        );
    }
    echo '</ul>';

    echo '<aside class="sfrfr-blog-archive-cta sfrfr-blog-cta">';
    echo '<p class="sfrfr-blog-cta__title">Задать вопрос</p>';
    echo '<p class="sfrfr-blog-cta__text">Напишите в MAX или оставьте заявку. Мы готовим документы и план — а подаёте через СФР или Госуслуги вы сами.</p>';
    echo sfrfr_blog_ask_cta_buttons_html();
    echo '</aside>';
});

/**
 * Граница услуги: готовим документы, подачу делает клиент.
 */
function sfrfr_blog_submission_disclaimer_html(): string
{
    return '<aside class="sfrfr-blog-disclaimer" role="note">'
        . '<p><strong>Как устроена помощь.</strong> '
        . 'Мы готовим документы, черновики и понятный план действий. '
        . 'А подаёте обращение через СФР, МФЦ или Госуслуги вы сами. '
        . 'Решение о пенсии и перерасчёте принимает только СФР.</p>'
        . '</aside>';
}

/**
 * End CTA + related posts before comments / after content.
 */
add_filter('the_content', static function (string $content): string {
    if (!is_singular('post') || !in_the_loop() || !is_main_query()) {
        return $content;
    }

    $prefix = '';
    if (strpos($content, 'sfrfr-blog-disclaimer') === false) {
        $prefix = sfrfr_blog_submission_disclaimer_html();
    }

    if (strpos($content, 'sfrfr-blog-cta--end') !== false) {
        return $prefix . $content;
    }

    $cta = '<aside class="sfrfr-blog-cta sfrfr-blog-cta--end">'
        . '<p class="sfrfr-blog-cta__title">Задать вопрос</p>'
        . '<p class="sfrfr-blog-cta__text">Ответим в MAX или по заявке. Мы готовим документы — а подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.</p>'
        . sfrfr_blog_ask_cta_buttons_html()
        . '</aside>';

    $related = '';
    $cats = wp_get_post_categories(get_the_ID());
    if ($cats) {
        $q = new WP_Query([
            'post_type' => 'post',
            'posts_per_page' => 4,
            'post__not_in' => [get_the_ID()],
            'category__in' => $cats,
            'ignore_sticky_posts' => true,
            'no_found_rows' => true,
        ]);
        if ($q->have_posts()) {
            $related .= '<section class="sfrfr-blog-related"><h2 class="sfrfr-blog-related__title">Похожие статьи</h2><ul>';
            while ($q->have_posts()) {
                $q->the_post();
                $related .= '<li><a href="' . esc_url(get_permalink()) . '">' . esc_html(get_the_title()) . '</a></li>';
            }
            $related .= '</ul></section>';
            wp_reset_postdata();
        }
    }

    return $prefix . $content . $cta . $related;
}, 20);
