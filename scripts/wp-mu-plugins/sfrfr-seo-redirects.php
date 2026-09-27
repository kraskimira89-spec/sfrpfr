<?php
/**
 * Plugin Name: SFRFR SEO Redirects
 * Description: 301 с тонких primer/analitika на pillar и hub (ТЗ-18, недели 3–6); статьи, склеенные с посадочными.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Статьи-дубли посадочных (план каннибализации 2026-09-27, п. 1, 3 и 4).
 * Посты в WP не удаляются: 301, вне sitemap и списков блога, ссылки в контенте ведут на посадочную.
 *
 * @return array<string,string> path without trailing slash → landing path with trailing slash
 */
function sfrfr_seo_merged_redirect_map(): array
{
    return [
        '/blog/chto-delat-esli-period-raboty-ne-uchten' => '/ne-uchli-stazh/',
        '/blog/kak-pomoch-rodstvenniku-proverit-stazh' => '/pomoch-rodstvenniku-proverit-stazh/',
        '/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda' => '/arhivnaya-spravka-stazh/',
    ];
}

/**
 * @return list<int>
 */
function sfrfr_seo_merged_post_ids(): array
{
    $ids = [];
    foreach (array_keys(sfrfr_seo_merged_redirect_map()) as $path) {
        $post = get_page_by_path(basename($path), OBJECT, 'post');
        if ($post instanceof WP_Post) {
            $ids[] = (int) $post->ID;
        }
    }
    return $ids;
}

function sfrfr_seo_merged_rewrite_links(string $content, string $currentPath): string
{
    foreach (sfrfr_seo_merged_redirect_map() as $from => $to) {
        $href = '(?:https?://(?:www\.)?proverkastaza\.ru)?' . preg_quote($from, '~') . '/?';
        if (trailingslashit($currentPath) === $to) {
            $content = (string) preg_replace('~<a\s[^>]*href=["\']' . $href . '["\'][^>]*>(.*?)</a>~is', '$1', $content);
            continue;
        }
        $content = (string) preg_replace('~(href=["\'])' . $href . '(["\'#?])~i', '${1}' . $to . '${2}', $content);
    }
    return $content;
}

add_filter('the_content', static function ($content) {
    if (!is_string($content) || is_admin()) {
        return $content;
    }
    $path = (string) wp_parse_url((string) ($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH);
    return sfrfr_seo_merged_rewrite_links($content, $path);
}, 20);

/**
 * @param array<string,mixed> $atts
 * @return array<string,mixed>
 */
add_filter('nav_menu_link_attributes', static function (array $atts): array {
    $href = (string) ($atts['href'] ?? '');
    $path = untrailingslashit((string) wp_parse_url($href, PHP_URL_PATH));
    $host = (string) wp_parse_url($href, PHP_URL_HOST);
    $merged = sfrfr_seo_merged_redirect_map();
    if ($path !== '' && isset($merged[$path]) && ($host === '' || preg_match('~^(?:www\.)?proverkastaza\.ru$~i', $host))) {
        $atts['href'] = $merged[$path];
    }
    return $atts;
}, 20);

/**
 * @param array<string,mixed> $args
 * @return array<string,mixed>
 */
add_filter('wp_sitemaps_posts_query_args', static function (array $args, string $postType): array {
    if ($postType !== 'post') {
        return $args;
    }
    $ids = sfrfr_seo_merged_post_ids();
    if ($ids) {
        $args['post__not_in'] = array_values(array_unique(array_merge(
            array_map('intval', (array) ($args['post__not_in'] ?? [])),
            $ids
        )));
    }
    return $args;
}, 20, 2);

add_action('pre_get_posts', static function (WP_Query $query): void {
    if (is_admin() || !$query->is_main_query() || !($query->is_home() || $query->is_archive() || $query->is_search())) {
        return;
    }
    $ids = sfrfr_seo_merged_post_ids();
    if ($ids) {
        $query->set('post__not_in', array_values(array_unique(array_merge(
            array_map('intval', (array) $query->get('post__not_in')),
            $ids
        ))));
    }
});

/**
 * @return array<string,string> path without trailing slash → target path with trailing slash under /blog/
 */
function sfrfr_seo_thin_redirect_map(): array
{
    $hub = [
        'ils' => '/blog/kak-proverit-stazh-v-vypiske-ils/',
        'zakaz' => '/blog/kak-zakazat-vypisku-ils/',
        'sverka' => '/blog/kak-sverit-trudovuyu-knizhku-i-ils/',
        'period' => '/ne-uchli-stazh/',
        'arhiv' => '/arhivnaya-spravka-stazh/',
        'dokumenty' => '/blog/kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr/',
        'otkaz' => '/blog/otkaz-sfr-chto-proverit-v-dokumentah/',
        'tipichnye' => '/blog/tipichnye-situacii-proverki-stazha/',
        'sfr' => '/blog/pochemu-reshenie-prinimaet-tolko-sfr/',
        'sever' => '/blog/severnyy-stazh-i-rayonnyy-koefficient/',
        'edv' => '/blog/edv-i-pensiya-chto-proveryat-otdelno/',
        'lgot' => '/blog/lgotnyy-i-pedagogicheskiy-stazh/',
        'fio' => '/blog/rashozhdeniya-fio-i-zapisi-trudovoy/',
    ];

    $slugs = [
        'primer-pedagogicheskiy-i-severnyy-stazh' => $hub['lgot'],
        'primer-rayonnyy-koefficient-i-severnyy-stazh' => $hub['sever'],
        'primer-proverka-nachisleniy-pered-pereraschetom' => $hub['ils'],
        'primer-dlinnyy-severnyy-stazh-s-1980-h' => $hub['sever'],
        'primer-neskolko-spravok-sfr-kak-sravnit' => $hub['sverka'],
        'primer-severnyy-stazh-i-periody-uhoda-za-detmi' => $hub['sever'],
        'primer-plan-proverki-pensii-po-shagam' => $hub['tipichnye'],
        'primer-rabotodatel-v-trudovoy-net-v-ils' => $hub['period'],
        'primer-kogda-nuzhna-arhivnaya-spravka' => $hub['arhiv'],
        'primer-edv-i-pereraschet-ne-putat' => $hub['edv'],
        'primer-dopolnitelnye-osnovaniya-i-stazh' => $hub['tipichnye'],
        'primer-slozhnyy-otraslevoy-stazh' => $hub['lgot'],
        'primer-povtornaya-proverka-posle-otveta-sfr' => $hub['otkaz'],
        'primer-edv-pri-sporah-po-stazhu' => $hub['edv'],
        'primer-tipovaya-sverka-ils-i-trudovoy' => $hub['sverka'],
        'primer-kogda-komplekt-dokumentov-okazyvaetsya-dostatochnym' => $hub['dokumenty'],
        'primer-rashozdenie-fio-v-dokumentah' => $hub['fio'],
        'primer-fio-edv-i-stazh-v-odnom-pakete' => $hub['edv'],
        'primer-pervichnaya-proverka-stazha' => $hub['ils'],
        'primer-voennyy-bilet-v-pakete-po-stazhu' => $hub['dokumenty'],
        'primer-rayony-priravnennye-k-severu' => $hub['sever'],
        'primer-oshibka-napisaniya-v-trudovoy' => $hub['fio'],
        'primer-pedagogicheskaya-lgotnaya-pensiya-i-sever' => $hub['lgot'],
        'primer-osparivanie-rascheta-bez-obeshchaniy' => $hub['sfr'],
        'primer-pereraschet-s-uchyotom-severnogo-stazha' => $hub['sever'],
        'analitika-sever-i-ils-chto-povtoryaetsya' => $hub['sever'],
        'analitika-deti-arkhiv-edv' => $hub['edv'],
        'analitika-otkaz-i-povtornoe-obrashchenie' => $hub['otkaz'],
        'analitika-fio-i-prioritety-dokumentov' => $hub['fio'],
        'analitika-sever-lgoty-i-ozhidaniya' => $hub['lgot'],
    ];

    $map = [];
    foreach ($slugs as $slug => $target) {
        $map['/blog/' . $slug] = $target;
    }
    return $map;
}

add_action('template_redirect', static function (): void {
    if (is_admin() || wp_doing_ajax() || (defined('REST_REQUEST') && REST_REQUEST)) {
        return;
    }
    $path = (string) wp_parse_url((string) ($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH);
    $path = untrailingslashit($path);
    if ($path === '') {
        return;
    }

    // Короткая ссылка /otzyv/ → карточка на Картах (форма Sprav /reviews/add/ больше не открывается).
    if ($path === '/otzyv') {
        wp_redirect('https://yandex.ru/maps/org/proverka_stazha/82469923047/reviews/?add-review=true', 302);
        exit;
    }

    if ($path === '/prezentaciya-dlya-deputata') {
        wp_safe_redirect(home_url('/partneram/'), 301);
        exit;
    }

    $merged = sfrfr_seo_merged_redirect_map();
    if (isset($merged[$path])) {
        wp_safe_redirect(home_url($merged[$path]), 301);
        exit;
    }

    $map = sfrfr_seo_thin_redirect_map();
    if (!isset($map[$path])) {
        return;
    }
    wp_safe_redirect(home_url($map[$path]), 301);
    exit;
}, 0);
