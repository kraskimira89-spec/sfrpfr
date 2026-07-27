<?php
/**
 * Очистить копирайт Astra в нижнем футере.
 * wp eval-file scripts/wp_hide_astra_copyright.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$settings = get_option('astra-settings', []);
if (!is_array($settings)) {
    $settings = [];
}

$changed = false;
foreach (['footer-copyright', 'footer-sml-section-1', 'footer-sml-section-2'] as $key) {
    if (!array_key_exists($key, $settings)) {
        continue;
    }
    $val = (string) $settings[$key];
    if ($val === '' || $val === ' ') {
        continue;
    }
    // Пустой HTML вместо копирайта Astra
    $settings[$key] = ' ';
    $changed = true;
    echo "CLEARED astra-settings[{$key}]\n";
}

if (!$changed) {
    // Явно задаём пустой copyright (Astra builder)
    $settings['footer-copyright'] = ' ';
    $changed = true;
    echo "SET astra-settings[footer-copyright]=empty\n";
}

if ($changed) {
    update_option('astra-settings', $settings);
    if (function_exists('astra_clear_theme_cache')) {
        astra_clear_theme_cache();
    }
    if (function_exists('wp_cache_flush')) {
        wp_cache_flush();
    }
}

echo "OK astra copyright\n";
