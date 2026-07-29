<?php
/**
 * Точечно пометить старую серию ситуаций/аналитики noindex, не меняя контент.
 *
 * wp eval-file scripts/wp_mark_thin_blog_noindex.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$termIds = [];
foreach (['situacii', 'analitika'] as $slug) {
    $term = get_term_by('slug', $slug, 'category');
    if ($term instanceof WP_Term) {
        $termIds[] = (int) $term->term_id;
    }
}

$postIds = $termIds ? get_posts([
    'post_type' => 'post',
    'post_status' => 'any',
    'numberposts' => -1,
    'fields' => 'ids',
    'category__in' => $termIds,
]) : [];

$updated = 0;
foreach ($postIds as $postId) {
    $postId = (int) $postId;
    if (
        !has_category('situacii', $postId)
        && !has_category('analitika', $postId)
    ) {
        continue;
    }
    update_post_meta($postId, '_sfrfr_noindex', '1');
    $updated++;
}

echo "NOINDEX thin_blog_posts={$updated}\n";
