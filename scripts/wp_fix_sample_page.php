<?php
/**
 * Убрать демо «Пример страницы» из индекса (ТЗ-10): draft + снять с меню.
 * wp eval-file scripts/wp_fix_sample_page.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$slugs = ['sample-page', 'primer-stranicy', 'example-page'];
$fixed = 0;
foreach ($slugs as $slug) {
    $page = get_page_by_path($slug);
    if (!$page) {
        echo "SKIP missing {$slug}\n";
        continue;
    }
    wp_update_post([
        'ID' => (int) $page->ID,
        'post_status' => 'draft',
    ]);
    echo "DRAFT {$slug} id=" . (int) $page->ID . "\n";
    $fixed++;
}

$menus = wp_get_nav_menus();
foreach ($menus as $menu) {
    $items = wp_get_nav_menu_items($menu->term_id);
    if (!is_array($items)) {
        continue;
    }
    foreach ($items as $item) {
        $url = (string) ($item->url ?? '');
        $title = mb_strtolower((string) ($item->title ?? ''));
        if (
            str_contains($url, 'sample-page')
            || str_contains($title, 'пример страниц')
            || str_contains($title, 'sample page')
        ) {
            wp_delete_post((int) $item->ID, true);
            echo "MENU remove item={$item->ID} menu={$menu->name}\n";
        }
    }
}

echo $fixed > 0 ? "OK sample pages drafted\n" : "OK nothing to draft\n";
