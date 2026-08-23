<?php
/**
 * Plugin Name: SFRFR Nav Mobile
 * Description: Бургер-меню на mobile — то же primary-меню, что в desktop-шапке.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Astra mobile drawer (`mobile_menu`) по умолчанию показывает список страниц.
 * Подставляем SFRFR Primary из location `primary`.
 *
 * @param array<string, mixed> $args
 * @return array<string, mixed>
 */
add_filter('wp_nav_menu_args', static function (array $args): array {
    if (($args['theme_location'] ?? '') !== 'mobile_menu') {
        return $args;
    }

    $locations = get_nav_menu_locations();
    if (!empty($locations['primary'])) {
        $args['menu'] = (int) $locations['primary'];
    }

    return $args;
}, 20);
