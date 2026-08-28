<?php
/**
 * Plugin Name: SFRFR Site Reviews Vitrine
 * Description: Опубликованные цитаты на /otzyvy/ и главной — JSON в HTML (без cross-origin fetch в MAX).
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * @return string
 */
function sfrfr_site_reviews_vitrine_api_url(int $limit): string
{
    $limit = max(1, min(24, $limit));
    if (function_exists('sfrfr_env')) {
        $custom = sfrfr_env('SFRFR_SITE_REVIEWS_VITRINE_URL');
        if ($custom !== '') {
            return str_replace('{limit}', (string) $limit, $custom);
        }
    }
    return 'http://127.0.0.1:8011/api/public/site-reviews?limit=' . $limit;
}

/**
 * @return list<array{id: string, text: string, source: string, published_at: mixed}>
 */
function sfrfr_site_reviews_vitrine_items(int $limit = 12): array
{
    $response = wp_remote_get(
        sfrfr_site_reviews_vitrine_api_url($limit),
        [
            'timeout' => 6,
            'headers' => ['Accept' => 'application/json'],
        ]
    );
    if (is_wp_error($response)) {
        return [];
    }
    $code = (int) wp_remote_retrieve_response_code($response);
    if ($code < 200 || $code >= 300) {
        return [];
    }
    $body = wp_remote_retrieve_body($response);
    $decoded = json_decode($body, true);
    if (!is_array($decoded)) {
        return [];
    }
    $rawItems = $decoded['items'] ?? [];
    if (!is_array($rawItems)) {
        return [];
    }
    $out = [];
    foreach ($rawItems as $raw) {
        if (!is_array($raw)) {
            continue;
        }
        $text = trim((string) ($raw['text'] ?? ''));
        $id = trim((string) ($raw['id'] ?? ''));
        if ($text === '' || $id === '') {
            continue;
        }
        $out[] = [
            'id' => $id,
            'text' => $text,
            'source' => (string) ($raw['source'] ?? ''),
            'published_at' => $raw['published_at'] ?? null,
        ];
    }
    return $out;
}

add_filter('the_content', static function (string $content): string {
    if (is_admin() || !is_singular('page')) {
        return $content;
    }
    $isOtzyvy = str_contains($content, 'id="sfrfr-otzyvy-page"')
        || str_contains($content, "id='sfrfr-otzyvy-page'");
    $isHome = str_contains($content, 'id="sfrfr-home-reviews"')
        || str_contains($content, "id='sfrfr-home-reviews'");
    if (!$isOtzyvy && !$isHome) {
        return $content;
    }
    if (str_contains($content, 'id="sfrfr-site-reviews-bootstrap"')) {
        return $content;
    }
    $limit = $isOtzyvy ? 12 : 3;
    $items = sfrfr_site_reviews_vitrine_items($limit);
    $json = wp_json_encode($items, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP);
    if (!is_string($json)) {
        $json = '[]';
    }
    $tag = '<script type="application/json" id="sfrfr-site-reviews-bootstrap">' . $json . '</script>';
    if (preg_match('/<script\b/i', $content)) {
        return (string) preg_replace('/<script\b/i', $tag . "\n<script", $content, 1);
    }
    return $content . "\n" . $tag;
}, 23);
