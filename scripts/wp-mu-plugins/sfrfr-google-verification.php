<?php
/**
 * Plugin Name: SFRFR Google site verification
 * Description: Метатег google-site-verification (Search Console).
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('wp_head', static function (): void {
    $token = '';
    $cfg = __DIR__ . '/sfrfr-google-verification.config.php';
    if (is_readable($cfg)) {
        $loaded = include $cfg;
        if (is_string($loaded)) {
            $token = trim($loaded);
        }
    }
    if ($token === '') {
        $token = trim((string) getenv('GOOGLE_SITE_VERIFICATION'));
    }
    if ($token === '') {
        return;
    }
    printf(
        "<meta name=\"google-site-verification\" content=\"%s\" />\n",
        esc_attr($token)
    );
}, 1);
