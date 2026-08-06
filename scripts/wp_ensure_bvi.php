<?php
/**
 * Включить Button visually impaired (BVI) и задать брендовые цвета кнопки.
 * wp eval-file scripts/wp_ensure_bvi.php
 */
if (!defined('ABSPATH')) {
    fwrite(STDERR, "ABSPATH missing\n");
    echo "0\n";
    return;
}

if (!function_exists('is_plugin_active')) {
    require_once ABSPATH . 'wp-admin/includes/plugin.php';
}

$plugin = 'button-visually-impaired/Button-visually-impaired.php';
if (!is_plugin_active($plugin)) {
    $alt = 'button-visually-impaired/button-visually-impaired.php';
    if (file_exists(WP_PLUGIN_DIR . '/' . $plugin)) {
        $r = activate_plugin($plugin);
    } elseif (file_exists(WP_PLUGIN_DIR . '/' . $alt)) {
        $plugin = $alt;
        $r = activate_plugin($plugin);
    } else {
        fwrite(STDERR, "BVI plugin files not found — install button-visually-impaired first\n");
        echo "0\n";
        return;
    }
    if (is_wp_error($r)) {
        fwrite(STDERR, $r->get_error_message() . "\n");
        echo "0\n";
        return;
    }
}

$defaults = [
    'bviActive' => 'true',
    'bviScriptLocation' => 'false',
    'bviTheme' => 'white',
    'bviFont' => 'arial',
    'bviFontSize' => '16',
    'bviLetterSpacing' => 'normal',
    'bviLineHeight' => 'normal',
    'bviImages' => 'true',
    'bviReload' => 'false',
    'bviSpeech' => 'true',
    'bviBuiltElements' => 'true',
    'bviPanelHide' => 'false',
    'bviPanelFixed' => 'true',
    'bviLang' => 'ru-RU',
    'bviLinkText' => 'Версия для слабовидящих',
    'bviLinkColor' => '#ffffff',
    'bviLinkBg' => '#1e4e79',
];

$current = get_option('bvi-option', []);
if (!is_array($current)) {
    $current = [];
}
$merged = array_merge($defaults, $current);
$merged['bviActive'] = 'true';
$merged['bviLang'] = 'ru-RU';
$merged['bviLinkText'] = 'Версия для слабовидящих';
$merged['bviLinkColor'] = '#ffffff';
$merged['bviLinkBg'] = '#1e4e79';
$merged['bviPanelFixed'] = 'true';

update_option('bvi-option', $merged);
echo "1\n";
