<?php
/**
 * Plugin Name: SFRFR SEO Schema
 * Description: Один LocalBusiness в JSON-LD (без microdata темы Astra), sameAs, FAQPage для FAQ-статьи, image статьи.
 */

if (!defined('ABSPATH')) {
    exit;
}

// Astra 4.x: фильтр гасит все свои microdata (Organization, WPHeader, WPFooter, CreativeWork, Person…).
add_filter('astra_schema_enabled', '__return_false');

/**
 * Публичные профили, проверенные на ответ 200. Часы работы не выводим,
 * пока владелец не подтвердит график.
 *
 * @return list<string>
 */
function sfrfr_seo_schema_same_as(): array
{
    return [
        'https://max.ru/channel_proverkastaza',
        'https://vk.com/proverkastaza',
        'https://yandex.ru/maps/org/proverka_stazha/82469923047/',
    ];
}

/**
 * Статьи, где вопросы и ответы видны на странице как «H2 с вопросом + абзац».
 *
 * @return list<string>
 */
function sfrfr_seo_schema_faq_slugs(): array
{
    return ['chastye-voprosy-o-proverke-stazha'];
}

/**
 * @return list<array<string, mixed>>
 */
function sfrfr_seo_schema_faq_from_content(string $content): array
{
    $pattern = '/<h2[^>]*>([^<]*\?)\s*<\/h2>\s*(?:<!--.*?-->\s*)*<p[^>]*>(.*?)<\/p>/isu';
    if (!preg_match_all($pattern, $content, $matches, PREG_SET_ORDER)) {
        return [];
    }
    $entities = [];
    foreach ($matches as $m) {
        $question = trim(html_entity_decode(wp_strip_all_tags($m[1]), ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        $answer = trim(html_entity_decode(wp_strip_all_tags($m[2]), ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        if ($question === '' || $answer === '') {
            continue;
        }
        $entities[] = [
            '@type' => 'Question',
            'name' => $question,
            'acceptedAnswer' => ['@type' => 'Answer', 'text' => $answer],
        ];
    }
    return $entities;
}

function sfrfr_seo_schema_article_image(int $postId): string
{
    $thumb = get_the_post_thumbnail_url($postId, 'full');
    if (is_string($thumb) && $thumb !== '') {
        return $thumb;
    }
    $content = (string) get_post_field('post_content', $postId);
    if (preg_match('/<img[^>]+src=["\']([^"\']+)["\']/i', $content, $m)) {
        return esc_url_raw($m[1]);
    }
    return '';
}

add_filter('sfrfr_seo_schema_graph', static function ($graph, $description = '', $canonical = '') {
    if (!is_array($graph)) {
        return $graph;
    }
    foreach ($graph as $i => $node) {
        if (!is_array($node)) {
            continue;
        }
        $type = $node['@type'] ?? '';
        if ($type === 'LocalBusiness') {
            $graph[$i]['sameAs'] = sfrfr_seo_schema_same_as();
        }
        if ($type === 'Article' && is_singular('post')) {
            $image = sfrfr_seo_schema_article_image((int) get_queried_object_id());
            if ($image !== '') {
                $graph[$i]['image'] = $image;
            }
        }
    }

    if (is_singular('post')) {
        $postId = (int) get_queried_object_id();
        $slug = (string) get_post_field('post_name', $postId);
        if (in_array($slug, sfrfr_seo_schema_faq_slugs(), true)) {
            $faq = sfrfr_seo_schema_faq_from_content((string) get_post_field('post_content', $postId));
            if ($faq !== []) {
                $graph[] = [
                    '@type' => 'FAQPage',
                    '@id' => (string) $canonical . '#faq',
                    'url' => (string) $canonical,
                    'name' => html_entity_decode(get_the_title($postId), ENT_QUOTES | ENT_HTML5, 'UTF-8'),
                    'mainEntity' => $faq,
                ];
            }
        }
    }
    return $graph;
}, 10, 3);
