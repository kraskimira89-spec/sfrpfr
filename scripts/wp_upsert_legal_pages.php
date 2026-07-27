<?php
/**
 * Создать/обновить юр. страницы (cookies и т.п.), если отсутствуют.
 * wp eval-file scripts/wp_upsert_legal_pages.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$assets = getenv('SFRFR_LEGAL_ASSETS') ?: (__DIR__ . '/assets');

$pages = [
    [
        'slug' => 'oferta',
        'title' => 'Публичная оферта',
        'file' => 'sfrfr-oferta.html',
    ],
    [
        'slug' => 'soglasie',
        'title' => 'Согласие на обработку персональных данных',
        'file' => 'sfrfr-consent.html',
    ],
    [
        'slug' => 'cookies',
        'title' => 'Политика cookies',
        'file' => 'sfrfr-cookies.html',
    ],
];

foreach ($pages as $p) {
    $path = rtrim($assets, '/\\') . DIRECTORY_SEPARATOR . $p['file'];
    if (!is_readable($path)) {
        echo "SKIP missing {$p['file']}\n";
        continue;
    }
    $content = (string) file_get_contents($path);
    $existing = get_page_by_path($p['slug']);
    if ($existing) {
        wp_update_post([
            'ID' => (int) $existing->ID,
            'post_title' => $p['title'],
            'post_content' => $content,
            'post_status' => 'publish',
        ]);
        echo "UPDATE {$p['slug']}=" . (int) $existing->ID . "\n";
        continue;
    }
    $id = wp_insert_post([
        'post_type' => 'page',
        'post_name' => $p['slug'],
        'post_title' => $p['title'],
        'post_content' => $content,
        'post_status' => 'publish',
    ], true);
    if (is_wp_error($id)) {
        throw new RuntimeException($id->get_error_message());
    }
    echo "CREATE {$p['slug']}={$id}\n";
}

echo "OK legal pages\n";
