<?php
$s = get_option('astra-settings', []);
foreach ((array) $s as $k => $v) {
    if (stripos($k, 'copy') !== false || stripos($k, 'footer') !== false || stripos($k, 'below') !== false) {
        $preview = is_string($v) ? substr($v, 0, 120) : json_encode($v);
        echo $k . ' => ' . $preview . PHP_EOL;
    }
}
echo 'theme_mod css=' . (string) get_theme_mod('custom_css_post_id') . PHP_EOL;
$css = (string) wp_get_custom_css();
echo 'wp_get_custom_css len=' . strlen($css) . PHP_EOL;
echo 'has hide=' . (strpos($css, 'section-below-footer-builder') !== false ? 'yes' : 'no') . PHP_EOL;
