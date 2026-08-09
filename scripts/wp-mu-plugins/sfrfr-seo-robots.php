<?php
/**
 * Plugin Name: SFRFR SEO robots (Yandex)
 * Description: Clean-param для ПДн и рекламных параметров URL; без влияния на обязательные пути WP.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_filter('robots_txt', static function (string $output, $public): string {
    if (!(bool) $public) {
        return $output;
    }
    $marker = '# SFRFR Yandex Clean-param';
    $block = "\n{$marker} (не индексировать варианты URL с ПДн и рекламными метками)\n"
        . "Clean-param: email&mail&e-mail&phone&tel&telephone&mobile&fio&name&firstname&lastname&snils&password&pass&token&access_token /\n"
        . "Clean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&yclid&ysclid&gclid&gad_source&gad_campaignid&gbraid&wbraid&fbclid&vkclid&mt_click_id&_erid&erid&_openstat&referral_code&campaign_code /\n";
    if (!str_contains($output, $marker)) {
        $output .= $block;
    }
    return $output;
}, 20, 2);
