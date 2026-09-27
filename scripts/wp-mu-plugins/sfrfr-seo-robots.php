<?php
/**
 * Plugin Name: SFRFR SEO robots (Yandex)
 * Description: Clean-param для ПДн и рекламных параметров URL; служебные URL (поиск, фиды, REST) закрыты от обхода.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_filter('robots_txt', static function (string $output, $public): string {
    if (!(bool) $public) {
        return $output;
    }
    // Правила должны стоять внутри группы «User-agent: *», а не после Sitemap.
    $serviceMarker = '# SFRFR service URLs';
    $serviceRules = "{$serviceMarker}\n"
        . "Disallow: /?s=\n"
        . "Disallow: /*?s=\n"
        . "Disallow: /search/\n"
        . "Disallow: /feed/\n"
        . "Disallow: /*/feed/\n"
        . "Disallow: /wp-json/\n";
    if (!str_contains($output, $serviceMarker)) {
        $withRules = preg_replace('/^(User-agent:\s*\*\s*\R)/mi', '$1' . $serviceRules, $output, 1, $count);
        if (is_string($withRules) && $count === 1) {
            $output = $withRules;
        } else {
            $output = "User-agent: *\n{$serviceRules}\n" . $output;
        }
    }

    $marker = '# SFRFR Yandex Clean-param';
    $block = "\n{$marker} (PDn + ad tracking query params; Yandex only)\n"
        . "Clean-param: email&mail&e-mail&phone&tel&telephone&mobile&fio&name&firstname&lastname&snils&password&pass&token&access_token /\n"
        . "Clean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&yclid&ysclid&gclid&gad_source&gad_campaignid&gbraid&wbraid&fbclid&vkclid&mt_click_id&_erid&erid&_openstat&referral_code&campaign_code /\n";
    if (!str_contains($output, $marker)) {
        $output .= $block;
    }
    return $output;
}, 20, 2);

add_action('template_redirect', static function (): void {
    if (is_feed() && !headers_sent()) {
        header('X-Robots-Tag: noindex, follow', true);
    }
}, 0);
