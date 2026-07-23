<?php
/**
 * Логотип и favicon WordPress (светлый фон).
 * wp eval-file scripts/wp_apply_branding.php
 * Опционально: SFRFR_LOGO_LIGHT=/path/to/sfrfr-logo-light.png
 */
$path = getenv('SFRFR_LOGO_LIGHT') ?: dirname(__FILE__) . '/assets/sfrfr-logo-light.png';
if (!is_readable($path)) {
    fwrite(STDERR, "Logo not found: {$path}\n");
    echo "0\n";
    return;
}

require_once ABSPATH . 'wp-admin/includes/file.php';
require_once ABSPATH . 'wp-admin/includes/media.php';
require_once ABSPATH . 'wp-admin/includes/image.php';

$filename = 'sfrfr-logo-light.png';
$existing = get_posts([
    'post_type' => 'attachment',
    'name' => sanitize_title(pathinfo($filename, PATHINFO_FILENAME)),
    'posts_per_page' => 1,
    'post_status' => 'inherit',
]);

$attach_id = 0;
if ($existing) {
    $attach_id = (int) $existing[0]->ID;
} else {
    $tmp = wp_tempnam($filename);
    if (!$tmp || !copy($path, $tmp)) {
        fwrite(STDERR, "Cannot copy logo to temp\n");
        echo "0\n";
        return;
    }
    $file_array = [
        'name' => $filename,
        'tmp_name' => $tmp,
    ];
    $attach_id = media_handle_sideload($file_array, 0, 'SFRFR logo (light)');
    if (is_wp_error($attach_id)) {
        @unlink($tmp);
        fwrite(STDERR, $attach_id->get_error_message() . "\n");
        echo "0\n";
        return;
    }
}

update_option('site_icon', $attach_id);
set_theme_mod('custom_logo', $attach_id);

// Astra: показать логотип в хедере, высота ~44px (ширина авто)
set_theme_mod('ast-header-retina-logo', '');
set_theme_mod('ast-header-responsive-logo-width', [
    'desktop' => 44,
    'tablet' => 44,
    'mobile' => 44,
]);
echo (int) $attach_id . "\n";
