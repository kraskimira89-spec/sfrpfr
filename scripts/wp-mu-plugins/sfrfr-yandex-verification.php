<?php
/**
 * Plugin Name: SFRFR Yandex domain verification
 * Description: Метатег подтверждения домена для Яндекс 360 / Вебмастер.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('wp_head', static function (): void {
    echo '<meta name="yandex-verification" content="24f89ecf6ff4297b" />' . "\n";
}, 1);
