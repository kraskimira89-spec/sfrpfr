<?php
/**
 * Короткие title ключевых страниц + меню «Вопросы» без якоря /#faq.
 * wp eval-file scripts/wp_ensure_sitelink_titles.php
 */
if (!defined('ABSPATH')) {
    fwrite(STDERR, "ABSPATH missing\n");
    echo "0\n";
    return;
}

$pages = [
    'tarify' => 'Тарифы',
    'kak-rabotaem' => 'Как это работает',
    'otzyvy' => 'Отзывы',
    'kontakty' => 'Контакты',
    'proverka-stazha' => 'Проверка стажа',
    'blog' => 'Статьи',
];

$updated = 0;
foreach ($pages as $slug => $title) {
    $page = get_page_by_path($slug);
    if (!$page instanceof WP_Post) {
        fwrite(STDERR, "skip missing page: {$slug}\n");
        continue;
    }
    $id = (int) $page->ID;
    $changed = false;
    if ((string) $page->post_title !== $title) {
        $r = wp_update_post([
            'ID' => $id,
            'post_title' => $title,
        ], true);
        if (is_wp_error($r)) {
            fwrite(STDERR, $r->get_error_message() . "\n");
            continue;
        }
        $changed = true;
    }
    foreach (['_sfrfr_seo_title', '_rank_math_title', '_yoast_wpseo_title'] as $metaKey) {
        if ((string) get_post_meta($id, $metaKey, true) !== $title) {
            update_post_meta($id, $metaKey, $title);
            $changed = true;
        }
    }
    if ($changed) {
        $updated++;
        echo "title ok: /{$slug}/ → {$title}\n";
    }
}

$faqUrl = home_url('/blog/chastye-voprosy-o-proverke-stazha/');
foreach (wp_get_nav_menus() as $menu) {
    $items = wp_get_nav_menu_items($menu->term_id);
    if (!is_array($items)) {
        continue;
    }
    foreach ($items as $item) {
        $title = trim((string) $item->title);
        $url = (string) $item->url;
        if ($title !== 'Вопросы') {
            continue;
        }
        if (!str_contains($url, '#faq')) {
            continue;
        }
        $itemId = wp_update_nav_menu_item($menu->term_id, (int) $item->ID, [
            'menu-item-title' => 'Вопросы',
            'menu-item-url' => $faqUrl,
            'menu-item-status' => 'publish',
            'menu-item-type' => 'custom',
        ]);
        if (!is_wp_error($itemId)) {
            echo "menu ok: Вопросы → {$faqUrl}\n";
            $updated++;
        }
    }
}

echo $updated > 0 ? "1\n" : "0\n";
