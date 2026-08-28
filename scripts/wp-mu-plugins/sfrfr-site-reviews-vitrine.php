<?php
/**
 * Plugin Name: SFRFR Site Reviews Vitrine
 * Description: Опубликованные цитаты на /otzyvy/ и главной — HTML с сервера (без JS fetch).
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

/**
 * @param list<array{id: string, text: string}> $items
 */
function sfrfr_site_reviews_vitrine_render_otzyvy(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $id = esc_attr((string) ($item['id'] ?? ''));
        $text = esc_html((string) ($item['text'] ?? ''));
        if ($id === '' || $text === '') {
            continue;
        }
        $html .= '<article class="sfrfr-card sfrfr-otzyvy-quote" id="review-' . $id . '">';
        $html .= '<p>«' . $text . '»</p>';
        $html .= '<p class="sfrfr-muted">Клиент сервиса, опубликовано с согласия</p>';
        $html .= '</article>';
    }
    return $html;
}

/**
 * @param list<array{id: string, text: string}> $items
 */
function sfrfr_site_reviews_vitrine_render_home(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $id = esc_attr((string) ($item['id'] ?? ''));
        $text = esc_html((string) ($item['text'] ?? ''));
        if ($id === '' || $text === '') {
            continue;
        }
        $html .= '<figure class="sfrfr-home-reviews__quote" id="review-' . $id . '">';
        $html .= '<p>«' . $text . '»</p>';
        $html .= '<footer>Клиент сервиса</footer>';
        $html .= '</figure>';
    }
    return $html;
}

/**
 * @param list<array{id: string, text: string}> $items
 */
function sfrfr_site_reviews_vitrine_bootstrap_tag(array $items): string
{
    $json = wp_json_encode($items, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP);
    if (!is_string($json)) {
        $json = '[]';
    }
    return '<script type="application/json" id="sfrfr-site-reviews-bootstrap">' . $json . '</script>';
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

    // Не кэшировать устаревший bootstrap из сохранённого контента.
    $content = (string) preg_replace(
        '/<script type="application\/json" id="sfrfr-site-reviews-bootstrap">.*?<\/script>\s*/s',
        '',
        $content
    );

    $limit = $isOtzyvy ? 12 : 3;
    $items = sfrfr_site_reviews_vitrine_items($limit);

    if ($isOtzyvy && $items !== []) {
        $content = (string) preg_replace(
            '/<h2 data-sfrfr-quotes-title>.*?<\/h2>/',
            '<h2 data-sfrfr-quotes-title>Что говорят клиенты</h2>',
            $content,
            1
        );
        $content = (string) preg_replace(
            '/<div class="sfrfr-otzyvy-policy" data-sfrfr-quotes-empty>/',
            '<div class="sfrfr-otzyvy-policy" data-sfrfr-quotes-empty hidden>',
            $content,
            1
        );
        $quotesHtml = sfrfr_site_reviews_vitrine_render_otzyvy($items);
        $replaced = preg_replace(
            '/<div class="sfrfr-otzyvy-quotes[^"]*"[^>]*data-sfrfr-quotes(?:="")?[^>]*>\s*<\/div>/',
            '<div class="sfrfr-otzyvy-quotes sfrfr-cards sfrfr-cards--row sfrfr-cards--2" data-sfrfr-quotes data-sfrfr-quotes-rendered="1">'
            . $quotesHtml
            . '</div>',
            $content,
            1,
            $count
        );
        if ($count > 0 && is_string($replaced)) {
            $content = $replaced;
        }
    }

    if ($isHome && $items !== []) {
        $quotesHtml = sfrfr_site_reviews_vitrine_render_home($items);
        $replaced = preg_replace(
            '/<div class="sfrfr-home-reviews__quotes" data-sfrfr-quotes>\s*<p class="sfrfr-home-reviews__empty" data-sfrfr-quotes-empty>.*?<\/p>\s*<\/div>/s',
            '<div class="sfrfr-home-reviews__quotes" data-sfrfr-quotes data-sfrfr-quotes-rendered="1">'
            . $quotesHtml
            . '</div>',
            $content,
            1,
            $count
        );
        if ($count > 0 && is_string($replaced)) {
            $content = $replaced;
        }
    }

    $bootstrap = sfrfr_site_reviews_vitrine_bootstrap_tag($items);
    if (preg_match('/<script\b/i', $content)) {
        return (string) preg_replace('/<script\b/i', $bootstrap . "\n<script", $content, 1);
    }
    return $content . "\n" . $bootstrap;
}, 23);
