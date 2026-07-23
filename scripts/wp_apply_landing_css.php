<?php
/**
 * Применяет CSS лендинга SFRFR в Custom CSS WordPress.
 * Использование: wp eval-file scripts/wp_apply_landing_css.php
 * Опционально: SFRFR_CSS_PATH=/path/to/sfrfr-landing.css
 */
$path = getenv('SFRFR_CSS_PATH') ?: dirname(__FILE__) . '/assets/sfrfr-landing.css';
if (!is_readable($path)) {
    fwrite(STDERR, "CSS not found: {$path}\n");
    echo "0\n";
    return;
}
$css = file_get_contents($path);
if ($css === false || $css === '') {
    echo "0\n";
    return;
}
$result = wp_update_custom_css_post($css);
if (is_wp_error($result)) {
    fwrite(STDERR, $result->get_error_message() . "\n");
    echo "0\n";
    return;
}
echo (int) $result->ID . "\n";
