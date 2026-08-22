<?php
/**
 * «Партнёрам» непосредственно перед «Контакты» в SFRFR Primary.
 *
 * wp eval-file scripts/wp_fix_partneram_menu_order.php
 */
$menu = wp_get_nav_menu_object('SFRFR Primary');
if (!$menu instanceof WP_Term) {
    echo "SKIP no menu\n";
    return;
}

$menuId = (int) $menu->term_id;
$items = wp_get_nav_menu_items($menuId) ?: [];
$top = [];
foreach ($items as $item) {
    if ((int) ($item->menu_item_parent ?? 0) === 0) {
        $top[] = $item;
    }
}

usort($top, static function ($a, $b): int {
    return ((int) $a->menu_order) <=> ((int) $b->menu_order);
});

$partneramId = 0;
$kontaktyPosition = null;
foreach ($top as $index => $item) {
    $title = (string) ($item->title ?? '');
    if ($title === 'Партнёрам') {
        $partneramId = (int) $item->ID;
    }
    if ($title === 'Контакты') {
        $kontaktyPosition = $index + 1;
    }
}

if ($partneramId <= 0 || $kontaktyPosition === null) {
    echo "SKIP partneram={$partneramId} kontaktyPos=" . ($kontaktyPosition ?? 'null') . "\n";
    return;
}

$targetPos = max(1, $kontaktyPosition - 1);
$result = wp_update_nav_menu_item($menuId, $partneramId, [
    'menu-item-title' => 'Партнёрам',
    'menu-item-url' => home_url('/partneram/'),
    'menu-item-status' => 'publish',
    'menu-item-type' => 'custom',
    'menu-item-object' => 'custom',
    'menu-item-position' => $targetPos,
]);

if (is_wp_error($result)) {
    echo 'FAIL ' . $result->get_error_message() . "\n";
    return;
}

echo "OK partneram={$partneramId} pos={$targetPos} before kontakty={$kontaktyPosition}\n";
