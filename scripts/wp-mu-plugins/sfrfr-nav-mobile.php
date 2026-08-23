<?php
/**
 * Plugin Name: SFRFR Nav Mobile
 * Description: Бургер-меню на mobile — то же primary-меню, что в desktop-шапке.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Astra mobile drawer: если mobile_menu не назначен, theme вызывает wp_page_menu()
 * (список всех страниц), а не wp_nav_menu — фильтр args не срабатывает.
 *
 * @param array<string, int> $locations
 * @return array<string, int>
 */
add_filter('theme_mod_nav_menu_locations', static function ($locations): array {
    if (!is_array($locations)) {
        $locations = [];
    }

    if (!empty($locations['mobile_menu']) || empty($locations['primary'])) {
        return $locations;
    }

    $locations['mobile_menu'] = (int) $locations['primary'];

    return $locations;
}, 20);

/**
 * Запасной путь: если Astra всё же вызовет wp_nav_menu для mobile_menu.
 *
 * @param array<string, mixed> $args
 * @return array<string, mixed>
 */
add_filter('wp_nav_menu_args', static function (array $args): array {
    $location = (string) ($args['theme_location'] ?? '');
    $menuId = (string) ($args['menu_id'] ?? '');
    $isMobileDrawer = $location === 'mobile_menu' || $menuId === 'ast-hf-mobile-menu';

    if (!$isMobileDrawer) {
        return $args;
    }

    $locations = get_nav_menu_locations();
    if (!empty($locations['primary'])) {
        $args['menu'] = (int) $locations['primary'];
        return $args;
    }

    $menu = wp_get_nav_menu_object('SFRFR Primary');
    if ($menu instanceof WP_Term) {
        $args['menu'] = (int) $menu->term_id;
    }

    return $args;
}, 20);
