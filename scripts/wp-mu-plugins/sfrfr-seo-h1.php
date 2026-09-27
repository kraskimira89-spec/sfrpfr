<?php
/**
 * Plugin Name: SFRFR SEO H1
 * Description: Один H1 на странице: если в контенте свой H1, заголовок записи темы Astra не выводится.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Ведущий H1 контента снимает the_content в sfrfr-seo-meta.php — тогда H1 даёт тема.
 * H1 внутри секций лендинга остаётся в контенте — тогда заголовок темы лишний.
 */
function sfrfr_seo_content_keeps_h1(string $content): bool
{
    $rest = preg_replace('/^\s*(?:<!--.*?-->\s*)*<h1\b[^>]*>.*?<\/h1>\s*/isu', '', $content, 1);
    return (bool) preg_match('/<h1\b/i', is_string($rest) ? $rest : $content);
}

add_filter('astra_the_title_enabled', static function ($enabled) {
    if (!$enabled || is_admin() || !is_page()) {
        return $enabled;
    }
    $pageId = (int) get_queried_object_id();
    if ($pageId <= 0 || (int) get_the_ID() !== $pageId) {
        return $enabled;
    }
    return sfrfr_seo_content_keeps_h1((string) get_post_field('post_content', $pageId)) ? false : $enabled;
});
