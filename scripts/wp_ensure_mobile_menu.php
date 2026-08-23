<?php
/**
 * Привязать SFRFR Primary к location mobile_menu (бургер Astra).
 * Без этого Astra вызывает wp_page_menu() — список всех страниц.
 */

if (!defined('ABSPATH')) {
    exit;
}

$menu = wp_get_nav_menu_object('SFRFR Primary');
if (!$menu instanceof WP_Term) {
    echo "SKIP no SFRFR Primary menu\n";
    return;
}

$locations = get_theme_mod('nav_menu_locations', []);
if (!is_array($locations)) {
    $locations = [];
}

$menuId = (int) $menu->term_id;
if ((int) ($locations['mobile_menu'] ?? 0) === $menuId) {
    echo "OK mobile_menu already={$menuId}\n";
    return;
}

$locations['mobile_menu'] = $menuId;
set_theme_mod('nav_menu_locations', $locations);
echo "SET mobile_menu={$menuId}\n";
