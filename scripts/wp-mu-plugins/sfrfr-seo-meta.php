<?php
/**
 * Plugin Name: SFRFR SEO Meta
 * Description: Единые description, canonical, Open Graph, JSON-LD и один H1 на публичной витрине.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Rank Math установлен, но frontend meta не является источником истины:
 * настройки live не версионируются. Sitemap плагина при этом не затрагивается.
 */
add_action('wp', static function (): void {
    remove_all_actions('rank_math/head');
}, 0);
remove_action('wp_head', 'rel_canonical');

function sfrfr_seo_limit(string $value, int $limit = 165): string
{
    $value = trim((string) preg_replace('/\s+/u', ' ', wp_strip_all_tags(strip_shortcodes($value))));
    if (function_exists('mb_strlen') && mb_strlen($value, 'UTF-8') > $limit) {
        return rtrim(mb_substr($value, 0, $limit - 1, 'UTF-8')) . '…';
    }
    if (strlen($value) > $limit) {
        return rtrim(substr($value, 0, $limit - 3)) . '...';
    }
    return $value;
}

function sfrfr_seo_description(): string
{
    if (is_front_page()) {
        return 'Проверка пенсионного стажа, выписки ИЛС и документов. Находим возможные расхождения и готовим понятный план обращения в СФР.';
    }
    if (is_home()) {
        return 'Практические статьи о проверке стажа, выписке ИЛС, архивных справках, документах и обращении в СФР.';
    }
    if (is_category()) {
        $term = get_queried_object();
        $name = $term instanceof WP_Term ? $term->name : 'проверке стажа';
        return sfrfr_seo_limit("Статьи по теме «{$name}»: инструкции, документы и частые ошибки при проверке пенсионного стажа и сведений ИЛС.");
    }
    if (is_singular()) {
        $postId = get_queried_object_id();
        $saved = (string) get_post_meta($postId, '_rank_math_description', true);
        if ($saved === '') {
            $saved = (string) get_post_meta($postId, '_yoast_wpseo_metadesc', true);
        }
        if ($saved !== '') {
            return sfrfr_seo_limit($saved);
        }

        $slug = (string) get_post_field('post_name', $postId);
        $pageDescriptions = [
            'oferta' => 'Условия оказания услуг сервиса «Проверка стажа»: состав сопровождения, порядок оплаты, права и обязанности сторон.',
            'politika-pdn' => 'Политика обработки персональных данных сервиса «Проверка стажа»: цели, основания, сроки и права пользователя.',
            'soglasie' => 'Согласие на обработку персональных данных при обращении в сервис «Проверка стажа».',
            'cookies' => 'Правила использования файлов браузера и аналитики на сайте сервиса «Проверка стажа».',
        ];
        if (isset($pageDescriptions[$slug])) {
            return $pageDescriptions[$slug];
        }

        $excerpt = (string) get_post_field('post_excerpt', $postId);
        if ($excerpt === '') {
            $excerpt = (string) get_post_field('post_content', $postId);
        }
        return sfrfr_seo_limit($excerpt);
    }
    return 'Проверка пенсионного стажа и документов: понятные инструкции и сопровождение подготовки обращения в СФР.';
}

function sfrfr_seo_canonical_url(): string
{
    if (is_front_page()) {
        return home_url('/');
    }
    if (is_home()) {
        $pageId = (int) get_option('page_for_posts');
        return $pageId > 0 ? (string) get_permalink($pageId) : home_url('/blog/');
    }
    if (is_category()) {
        $url = get_term_link(get_queried_object());
        if (!is_wp_error($url)) {
            return (string) $url;
        }
    }
    if (is_singular()) {
        return (string) get_permalink();
    }
    return home_url((string) wp_parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH));
}

function sfrfr_seo_social_image(): string
{
    $logoId = (int) get_theme_mod('custom_logo');
    if ($logoId > 0) {
        $url = wp_get_attachment_image_url($logoId, 'full');
        if (is_string($url)) {
            return $url;
        }
    }
    return (string) get_site_icon_url(512);
}

/**
 * @return array<int, array<string, mixed>>
 */
function sfrfr_seo_schema_graph(string $description, string $canonical): array
{
    $site = home_url('/');
    $orgId = $site . '#organization';
    $websiteId = $site . '#website';
    $logo = sfrfr_seo_social_image();
    $graph = [
        [
            '@type' => 'Organization',
            '@id' => $orgId,
            'name' => 'ООО «ПОД ПРИСМОТРОМ»',
            'url' => $site,
        ],
        [
            '@type' => 'WebSite',
            '@id' => $websiteId,
            'url' => $site,
            'name' => 'Проверка стажа',
            'inLanguage' => 'ru-RU',
            'publisher' => ['@id' => $orgId],
        ],
    ];
    if ($logo !== '') {
        $graph[0]['logo'] = [
            '@type' => 'ImageObject',
            'url' => $logo,
        ];
    }

    if (is_front_page()) {
        $graph[] = [
            '@type' => 'Service',
            '@id' => $site . '#service',
            'name' => 'Проверка пенсионного стажа и документов',
            'description' => $description,
            'url' => $canonical,
            'provider' => ['@id' => $orgId],
            'areaServed' => ['@type' => 'Country', 'name' => 'Россия'],
        ];
    }

    if (is_singular('post')) {
        $postId = get_queried_object_id();
        $article = [
            '@type' => 'Article',
            '@id' => $canonical . '#article',
            'mainEntityOfPage' => $canonical,
            'headline' => get_the_title($postId),
            'description' => $description,
            'datePublished' => get_the_date(DATE_W3C, $postId),
            'dateModified' => get_the_modified_date(DATE_W3C, $postId),
            'inLanguage' => 'ru-RU',
            'author' => ['@id' => $orgId],
            'publisher' => ['@id' => $orgId],
        ];
        if ($logo !== '') {
            $article['image'] = $logo;
        }
        $graph[] = $article;
        $graph[] = [
            '@type' => 'BreadcrumbList',
            '@id' => $canonical . '#breadcrumbs',
            'itemListElement' => [
                [
                    '@type' => 'ListItem',
                    'position' => 1,
                    'name' => 'Главная',
                    'item' => $site,
                ],
                [
                    '@type' => 'ListItem',
                    'position' => 2,
                    'name' => 'Статьи',
                    'item' => home_url('/blog/'),
                ],
                [
                    '@type' => 'ListItem',
                    'position' => 3,
                    'name' => get_the_title($postId),
                    'item' => $canonical,
                ],
            ],
        ];
    }
    return $graph;
}

add_action('wp_head', static function (): void {
    if (is_admin() || is_feed() || is_robots() || is_trackback()) {
        return;
    }
    if (!is_front_page() && !is_home() && !is_category() && !is_singular()) {
        return;
    }

    $description = sfrfr_seo_description();
    $canonical = sfrfr_seo_canonical_url();
    $title = wp_get_document_title();
    $image = sfrfr_seo_social_image();
    $type = is_singular('post') ? 'article' : 'website';

    echo "\n<!-- SFRFR SEO Meta -->\n";
    printf("<meta name=\"description\" content=\"%s\" />\n", esc_attr($description));
    printf("<link rel=\"canonical\" href=\"%s\" />\n", esc_url($canonical));
    printf("<meta property=\"og:locale\" content=\"ru_RU\" />\n");
    printf("<meta property=\"og:type\" content=\"%s\" />\n", esc_attr($type));
    printf("<meta property=\"og:site_name\" content=\"Проверка стажа\" />\n");
    printf("<meta property=\"og:title\" content=\"%s\" />\n", esc_attr($title));
    printf("<meta property=\"og:description\" content=\"%s\" />\n", esc_attr($description));
    printf("<meta property=\"og:url\" content=\"%s\" />\n", esc_url($canonical));
    if ($image !== '') {
        printf("<meta property=\"og:image\" content=\"%s\" />\n", esc_url($image));
        printf("<meta name=\"twitter:card\" content=\"summary_large_image\" />\n");
    } else {
        printf("<meta name=\"twitter:card\" content=\"summary\" />\n");
    }
    if (is_singular('post')) {
        printf("<meta property=\"article:published_time\" content=\"%s\" />\n", esc_attr(get_the_date(DATE_W3C)));
        printf("<meta property=\"article:modified_time\" content=\"%s\" />\n", esc_attr(get_the_modified_date(DATE_W3C)));
    }

    $schema = [
        '@context' => 'https://schema.org',
        '@graph' => sfrfr_seo_schema_graph($description, $canonical),
    ];
    echo '<script type="application/ld+json">'
        . wp_json_encode($schema, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)
        . "</script>\n";
}, 2);

/**
 * Astra уже выводит post_title как H1. Убираем только первый H1 из тела записи,
 * оставляя исходные HTML-ассеты пригодными для чтения и повторного сида.
 */
add_filter('the_content', static function (string $content): string {
    if (!is_singular('post') || !in_the_loop() || !is_main_query()) {
        return $content;
    }
    $updated = preg_replace('/^\s*<h1\b[^>]*>.*?<\/h1>\s*/isu', '', $content, 1);
    return is_string($updated) ? $updated : $content;
}, 5);
