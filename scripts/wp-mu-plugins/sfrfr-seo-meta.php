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

function sfrfr_seo_is_noindex(): bool
{
    if (is_category(['situacii', 'analitika'])) {
        return true;
    }
    if (!is_singular('post')) {
        return false;
    }
    $postId = get_queried_object_id();
    if ((string) get_post_meta($postId, '_sfrfr_noindex', true) === '1') {
        return true;
    }
    return has_category(['situacii', 'analitika'], $postId);
}

add_action('send_headers', static function (): void {
    if (sfrfr_seo_is_noindex() && !headers_sent()) {
        header('X-Robots-Tag: noindex, follow', true);
    }
});

/**
 * Единый URL главной: /glavnaya/ → /.
 */
add_action('template_redirect', static function (): void {
    if (is_admin() || wp_doing_ajax() || (defined('REST_REQUEST') && REST_REQUEST)) {
        return;
    }
    $path = (string) wp_parse_url((string) ($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH);
    $path = untrailingslashit($path);
    if ($path === '/glavnaya') {
        wp_safe_redirect(home_url('/'), 301);
        exit;
    }
}, 1);

/**
 * Не включать тонкие ситуации/аналитику в WordPress sitemap.
 *
 * @param array<string,mixed> $args
 * @return array<string,mixed>
 */
add_filter('wp_sitemaps_posts_query_args', static function (array $args, string $postType): array {
    if ($postType !== 'post') {
        return $args;
    }
    $args['meta_query'] = [
        'relation' => 'OR',
        [
            'key' => '_sfrfr_noindex',
            'compare' => 'NOT EXISTS',
        ],
        [
            'key' => '_sfrfr_noindex',
            'value' => '1',
            'compare' => '!=',
        ],
    ];
    $excludeCats = [];
    foreach (['situacii', 'analitika'] as $slug) {
        $term = get_term_by('slug', $slug, 'category');
        if ($term instanceof WP_Term) {
            $excludeCats[] = (int) $term->term_id;
        }
    }
    if ($excludeCats) {
        $args['category__not_in'] = array_values(array_unique(array_merge(
            array_map('intval', (array) ($args['category__not_in'] ?? [])),
            $excludeCats
        )));
    }
    return $args;
}, 10, 2);

/**
 * Не включать временные архивы тонких серий в taxonomy sitemap.
 *
 * @param array<string,mixed> $args
 * @return array<string,mixed>
 */
add_filter('wp_sitemaps_taxonomies_query_args', static function (array $args, string $taxonomy): array {
    if ($taxonomy !== 'category') {
        return $args;
    }
    $exclude = [];
    foreach (['situacii', 'analitika'] as $slug) {
        $term = get_term_by('slug', $slug, 'category');
        if ($term instanceof WP_Term) {
            $exclude[] = (int) $term->term_id;
        }
    }
    if ($exclude) {
        $args['exclude'] = array_values(array_unique(array_merge(
            array_map('intval', (array) ($args['exclude'] ?? [])),
            $exclude
        )));
    }
    return $args;
}, 10, 2);

function sfrfr_seo_limit(string $value, int $limit = 165): string
{
    $value = wp_check_invalid_utf8($value, true);
    $normalized = preg_replace('/\s+/', ' ', wp_strip_all_tags(strip_shortcodes($value)));
    $value = trim(is_string($normalized) ? $normalized : $value);
    if ($value === '') {
        return '';
    }
    // Считать лимит в символах UTF-8. Никогда не резать Cyrillic через substr() по байтам —
    // иначе esc_attr() на фронте отдаёт пустой content.
    if (function_exists('mb_strlen') && function_exists('mb_substr')) {
        if (mb_strlen($value, 'UTF-8') > $limit) {
            $cut = rtrim(mb_substr($value, 0, max(1, $limit - 1), 'UTF-8'));
            return wp_check_invalid_utf8($cut, true) . '…';
        }
        return $value;
    }
    if (strlen($value) > $limit) {
        $cut = substr($value, 0, max(1, $limit - 3));
        $cut = wp_check_invalid_utf8($cut, true);
        return rtrim($cut) . '...';
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
        $name = $term instanceof WP_Term ? (string) $term->name : 'проверке стажа';
        $name = wp_check_invalid_utf8($name, true);
        if ($name === '') {
            $name = 'проверке стажа';
        }
        return sfrfr_seo_limit("Статьи по теме «{$name}»: инструкции, документы и частые ошибки при проверке пенсионного стажа и сведений ИЛС.");
    }
    if (is_singular()) {
        $postId = get_queried_object_id();
        foreach (['_sfrfr_seo_description', '_rank_math_description', '_yoast_wpseo_metadesc'] as $metaKey) {
            $saved = (string) get_post_meta($postId, $metaKey, true);
            $saved = trim(wp_check_invalid_utf8($saved, true));
            if ($saved !== '') {
                $limited = sfrfr_seo_limit($saved);
                if ($limited !== '') {
                    return $limited;
                }
            }
        }

        $slug = (string) get_post_field('post_name', $postId);
        $pageDescriptions = [
            'oferta' => 'Условия оказания услуг сервиса «Проверка стажа»: состав сопровождения, порядок оплаты, права и обязанности сторон.',
            'politika-pdn' => 'Политика обработки персональных данных сервиса «Проверка стажа»: цели, основания, сроки и права пользователя.',
            'soglasie' => 'Согласие на обработку персональных данных при обращении в сервис «Проверка стажа».',
            'cookies' => 'Правила использования файлов браузера и аналитики на сайте сервиса «Проверка стажа».',
            'kak-proverit-stazh-v-vypiske-ils' => 'Как читать выписку ИЛС, сверить периоды работы с трудовой и понять, каких подтверждений не хватает перед обращением в СФР.',
            'kak-sverit-trudovuyu-knizhku-i-ils' => 'Пошаговая сверка трудовой книжки и выписки ИЛС: как найти расхождения и что подготовить для уточнения сведений.',
            'chto-delat-esli-period-raboty-ne-uchten' => 'Что делать, если период работы не отражён в ИЛС: порядок подтверждения, архивные справки и обращение в СФР.',
            'arhivnaya-spravka-dlya-sfr-zachem-i-kuda' => 'Когда нужна архивная справка для СФР, куда обращаться при ликвидации работодателя и какие сведения обычно запрашивают.',
            'tipichnye-situacii-proverki-stazha' => 'Типичные ситуации при проверке стажа: что сверять в документах и какой следующий шаг выбрать без обещания перерасчёта.',
            'kak-pomoch-rodstvenniku-proverit-stazh' => 'Как родственнику помочь проверить стаж: согласие, документы, каналы связи и границы участия без передачи сканов в открытый чат.',
            'chto-vy-poluchite-posle-proverki-stazha' => 'Что входит в результат проверки стажа: разбор документов, план действий и границы услуги сервиса «Проверка стажа».',
            'kak-rabotat-v-max-i-lichnom-kabinete' => 'Как связаны MAX и личный кабинет на сайте: что можно обсуждать в мессенджере и куда загружать документы.',
            'chastye-voprosy-o-proverke-stazha' => 'Частые вопросы о проверке стажа и ИЛС: документы, сроки, каналы обращения и типичные ограничения услуги.',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr' => 'Какие документы собрать до обращения в СФР при проверке стажа: минимальный комплект и порядок подготовки.',
            'kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc' => 'Как подготовиться к подаче заявления через Госуслуги или МФЦ: комплект, порядок и типичные ошибки.',
            'otkaz-sfr-chto-proverit-v-dokumentah' => 'Что проверить после отказа СФР: текст решения, документы и безопасные следующие шаги без гарантии исхода.',
            'pensiya-po-invalidnosti-i-stazh-na-chto-smotret' => 'Пенсия по инвалидности и стаж: что сверять отдельно и как не смешивать разные основания выплат.',
            'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya' => 'Чем диагностика стажа отличается от сопровождения обращения: состав работ, результат и ограничения.',
            'pochemu-reshenie-prinimaet-tolko-sfr' => 'Почему решение о перерасчёте принимает только СФР: роль сервиса, границы помощи и что клиент делает самостоятельно.',
            'chek-list-pered-zapisju-v-mfc' => 'Чек-лист перед записью в МФЦ по вопросам стажа и ИЛС: документы, копии и что уточнить заранее.',
            'severnyy-stazh-i-rayonnyy-koefficient' => 'Северный стаж и районный коэффициент: что сверять в документах и выписке ИЛС, не путая разные основания.',
            'edv-i-pensiya-chto-proveryat-otdelno' => 'ЕДВ и пенсия: что относится к стажу, а что проверять отдельно, чтобы не смешивать разные решения СФР.',
            'lgotnyy-i-pedagogicheskiy-stazh' => 'Льготный и педагогический стаж: какие периоды уточнять отдельно и какие документы обычно нужны для сверки.',
            'rashozhdeniya-fio-i-zapisi-trudovoy' => 'Расхождения ФИО и ошибки в трудовой: как сверить записи и какие подтверждения обычно нужны до обращения в СФР.',
        ];
        if (isset($pageDescriptions[$slug])) {
            return $pageDescriptions[$slug];
        }

        $excerpt = trim(wp_check_invalid_utf8((string) get_post_field('post_excerpt', $postId), true));
        if ($excerpt === '') {
            $excerpt = trim(wp_check_invalid_utf8((string) get_post_field('post_content', $postId), true));
        }
        $limited = sfrfr_seo_limit($excerpt);
        if ($limited !== '') {
            return $limited;
        }
        $title = trim(wp_check_invalid_utf8((string) get_the_title($postId), true));
        if ($title !== '') {
            return sfrfr_seo_limit("{$title}: практическая инструкция сервиса «Проверка стажа» без обещания перерасчёта.");
        }
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
    if (sfrfr_seo_is_noindex()) {
        echo "<meta name=\"robots\" content=\"noindex, follow\" />\n";
    }
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
