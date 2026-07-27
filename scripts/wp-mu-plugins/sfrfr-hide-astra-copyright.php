<?php
/**
 * Plugin Name: SFRFR Hide Astra Copyright
 * Description: Убирает нижнюю полоску «Авторское право © … Тема Astra».
 */

if (!defined('ABSPATH')) {
    exit;
}

/** Пустой текст копирайта (Astra builder / classic). */
add_filter('astra_get_option_footer-copyright', static function () {
    return '';
}, 99);
add_filter('astra_footer_copyright', static function () {
    return '';
}, 99);

/** CSS в самом конце head — перекрывает dynamic CSS Astra. */
add_action('wp_head', static function (): void {
    echo '<style id="sfrfr-hide-astra-copyright">'
        . '.site-below-footer-wrap[data-section="section-below-footer-builder"],'
        . '.site-below-footer-wrap,'
        . '.ast-footer-copyright,'
        . '.ast-footer-copyright.ast-builder-layout-element{'
        . 'display:none!important;visibility:hidden!important;height:0!important;'
        . 'min-height:0!important;max-height:0!important;overflow:hidden!important;'
        . 'padding:0!important;margin:0!important;border:0!important;}'
        . '</style>' . "\n";
}, 9999);
