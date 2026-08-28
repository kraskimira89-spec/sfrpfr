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
 * @return list<array<string, mixed>>
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
        $byline = trim((string) ($raw['byline'] ?? ''));
        if ($byline === '') {
            continue;
        }
        $out[] = [
            'id' => $id,
            'text' => $text,
            'source' => (string) ($raw['source'] ?? ''),
            'author_label' => (string) ($raw['author_label'] ?? ''),
            'byline' => $byline,
            'published_at' => $raw['published_at'] ?? null,
        ];
    }
    return $out;
}

function sfrfr_site_reviews_vitrine_focus_id(): string
{
    if (!isset($_GET['review'])) {
        return '';
    }
    return sanitize_text_field(wp_unslash((string) $_GET['review']));
}

/**
 * @param list<array<string, mixed>> $items
 */
function sfrfr_site_reviews_vitrine_render_otzyvy(array $items, string $focusId = ''): string
{
    $html = '';
    foreach ($items as $item) {
        $id = esc_attr((string) ($item['id'] ?? ''));
        $text = esc_html((string) ($item['text'] ?? ''));
        $byline = esc_html((string) ($item['byline'] ?? ''));
        if ($id === '' || $text === '' || $byline === '') {
            continue;
        }
        $classes = 'sfrfr-card sfrfr-otzyvy-quote';
        if ($focusId !== '' && hash_equals($focusId, (string) ($item['id'] ?? ''))) {
            $classes .= ' sfrfr-otzyvy-quote--highlight';
        }
        $html .= '<article class="' . $classes . '" id="review-' . $id . '" tabindex="-1">';
        $html .= '<p>«' . $text . '»</p>';
        $html .= '<p class="sfrfr-muted sfrfr-otzyvy-quote-author">— ' . $byline . '</p>';
        $html .= '</article>';
    }
    return $html;
}

/**
 * @param list<array<string, mixed>> $items
 */
function sfrfr_site_reviews_vitrine_render_home(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $id = esc_attr((string) ($item['id'] ?? ''));
        $text = esc_html((string) ($item['text'] ?? ''));
        $byline = esc_html((string) ($item['byline'] ?? ''));
        if ($id === '' || $text === '' || $byline === '') {
            continue;
        }
        $html .= '<figure class="sfrfr-home-reviews__quote" id="review-' . $id . '">';
        $html .= '<p>«' . $text . '»</p>';
        $html .= '<footer>— ' . $byline . '</footer>';
        $html .= '</figure>';
    }
    return $html;
}

/**
 * @param list<array<string, mixed>> $items
 */
function sfrfr_site_reviews_vitrine_bootstrap_tag(array $items): string
{
    $json = wp_json_encode($items, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP);
    if (!is_string($json)) {
        $json = '[]';
    }
    return '<script type="application/json" id="sfrfr-site-reviews-bootstrap">' . $json . '</script>';
}

function sfrfr_site_reviews_vitrine_scroll_snippet(string $focusId): string
{
    if ($focusId === '') {
        return '';
    }
    $jsonId = wp_json_encode($focusId);
    if (!is_string($jsonId)) {
        return '';
    }
    return '<script>(function(){var id=' . $jsonId . ';function go(){var el=document.getElementById("review-"+id);if(!el)return;el.classList.add("sfrfr-otzyvy-quote--highlight");try{el.scrollIntoView({block:"center",behavior:"auto"});}catch(e){location.hash="review-"+id;}}if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",go);}else{setTimeout(go,0);}})();</script>';
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

    $content = (string) preg_replace(
        '/<script type="application\/json" id="sfrfr-site-reviews-bootstrap">.*?<\/script>\s*/s',
        '',
        $content
    );
    $content = (string) preg_replace(
        '/<script>\(function\(\)\{var id=.*?sfrfr_site_reviews_vitrine_scroll.*?\}\)\(\);<\/script>\s*/s',
        '',
        $content
    );

    $limit = $isOtzyvy ? 12 : 3;
    $items = sfrfr_site_reviews_vitrine_items($limit);
    $focusId = $isOtzyvy ? sfrfr_site_reviews_vitrine_focus_id() : '';
    $scrollSnippet = '';

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
        $quotesHtml = sfrfr_site_reviews_vitrine_render_otzyvy($items, $focusId);
        $replaced = preg_replace(
            '/<div class="sfrfr-otzyvy-quotes[^"]*"[^>]*data-sfrfr-quotes(?:="")?[^>]*>[\s\S]*?<\/div>\s*(?=<p class="sfrfr-note sfrfr-otzyvy-review-miss"|<\/div>)/',
            '<div class="sfrfr-otzyvy-quotes sfrfr-cards sfrfr-cards--row sfrfr-cards--2" data-sfrfr-quotes data-sfrfr-quotes-rendered="1">'
            . $quotesHtml
            . '</div>'
            . "\n",
            $content,
            1,
            $count
        );
        if ($count > 0 && is_string($replaced)) {
            $content = $replaced;
        }
        $scrollSnippet = sfrfr_site_reviews_vitrine_scroll_snippet($focusId);
    }

    if ($isHome && $items !== []) {
        $quotesHtml = sfrfr_site_reviews_vitrine_render_home($items);
        $replaced = preg_replace(
            '/<div class="sfrfr-home-reviews__quotes" data-sfrfr-quotes[^>]*>[\s\S]*?<\/div>/s',
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
    $inject = $bootstrap . ($scrollSnippet !== '' ? "\n" . $scrollSnippet : '');
    if (preg_match('/<script\b/i', $content)) {
        return (string) preg_replace('/<script\b/i', $inject . "\n<script", $content, 1);
    }
    return $content . "\n" . $inject;
}, 23);
