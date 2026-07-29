<?php
/**
 * Plugin Name: SFRFR SEO robots (Yandex)
 * Description: Clean-param для ПДн-параметров URL; без влияния на обязательные пути WP.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_filter('robots_txt', static function (string $output, $public): string {
    if (!(bool) $public) {
        return $output;
    }
    $block = "\n# SFRFR Yandex Clean-param (не индексировать ПДн в query)\n"
        . "Clean-param: email&mail&e-mail&phone&tel&telephone&mobile&fio&name&firstname&lastname&snils&password&pass&token&access_token /\n";
    if (!str_contains($output, 'Clean-param:')) {
        $output .= $block;
    }
    return $output;
}, 20, 2);
