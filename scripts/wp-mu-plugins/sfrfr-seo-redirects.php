<?php
/**
 * Plugin Name: SFRFR SEO Redirects
 * Description: 301 с тонких primer/analitika на pillar и hub (ТЗ-18, недели 3–6).
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * @return array<string,string> path without trailing slash → target path with trailing slash under /blog/
 */
function sfrfr_seo_thin_redirect_map(): array
{
    $hub = [
        'ils' => '/blog/kak-proverit-stazh-v-vypiske-ils/',
        'zakaz' => '/blog/kak-zakazat-vypisku-ils/',
        'sverka' => '/blog/kak-sverit-trudovuyu-knizhku-i-ils/',
        'period' => '/blog/chto-delat-esli-period-raboty-ne-uchten/',
        'arhiv' => '/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/',
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

    $map = sfrfr_seo_thin_redirect_map();
    if (!isset($map[$path])) {
        return;
    }
    wp_safe_redirect(home_url($map[$path]), 301);
    exit;
}, 0);
