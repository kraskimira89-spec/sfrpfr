<?php
/**
 * Plugin Name: SFRFR Blog UI (ТЗ-11 §13)
 * Description: Чипы рубрик, TOC, CTA mid/end на блоге.
 * MU-plugin: copy to wp-content/mu-plugins/ (or symlink from /opt/sfrfr/scripts/wp-mu-plugins/).
 */

if (!defined('ABSPATH')) {
    exit;
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
        'dlya-rodstvennikov' => 'Родственникам',
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
    $ver = '20260726';
    wp_enqueue_style('sfrfr-blog-ui', $base . '/blog-ui.css', [], $ver);
    if (is_singular('post')) {
        wp_enqueue_script('sfrfr-blog-ui', $base . '/blog-ui.js', [], $ver, true);
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
    echo '<p class="sfrfr-blog-cta__title">Готовы проверить своё дело?</p>';
    echo '<p class="sfrfr-blog-cta__text">Выберите MAX или веб-кабинет — документы загружаются только в защищённый контур.</p>';
    echo '<a class="sfrfr-blog-cta__btn" href="' . esc_url(home_url('/#kak-rabotat')) . '">Начать проверку</a>';
    echo '</aside>';
});

/**
 * End CTA + related posts before comments / after content.
 */
add_filter('the_content', static function (string $content): string {
    if (!is_singular('post') || !in_the_loop() || !is_main_query()) {
        return $content;
    }
    if (strpos($content, 'sfrfr-blog-cta--end') !== false) {
        return $content;
    }

    $cta = '<aside class="sfrfr-blog-cta sfrfr-blog-cta--end">'
        . '<p class="sfrfr-blog-cta__title">Начать проверку</p>'
        . '<p class="sfrfr-blog-cta__text">Одинаковые шаги в MAX и в браузере. Решение всегда принимает СФР.</p>'
        . '<a class="sfrfr-blog-cta__btn" href="' . esc_url(home_url('/#kak-rabotat')) . '">Выбрать канал</a>'
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

    return $content . $cta . $related;
}, 20);
