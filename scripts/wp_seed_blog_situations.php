<?php
/**
 * Серия обезличенных ситуаций DeepSeek + аналитика каждые 5.
 * Запуск: wp --path=SITE eval-file scripts/wp_seed_blog_situations.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$assets = getenv('SFRFR_SITUATIONS_HTML')
    ?: (__DIR__ . '/assets/blog/situations/html');
$indexPath = rtrim($assets, '/\\') . DIRECTORY_SEPARATOR . 'index.json';
if (!is_readable($indexPath)) {
    throw new RuntimeException("Missing index.json. Run: python scripts/generate_blog_situations.py");
}

$index = json_decode((string) file_get_contents($indexPath), true);
if (!is_array($index)) {
    throw new RuntimeException('Bad index.json');
}

$homeUrl = home_url('/');
$disclaimer = '<p class="sfrfr-article-disclaimer"><em>Не являемся СФР. Решение о перерасчёте принимает СФР. Материал носит справочный характер. Примеры обезличены.</em></p>';

$maxUrl = getenv('MAX_CHAT_URL') ?: getenv('MAX_PUBLIC_BOT_URL') ?: 'https://max.ru/id8905998693_1_bot';
$maxUrl = htmlspecialchars((string) $maxUrl, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

$ctaBlock = <<<HTML
<div class="sfrfr-article-cta">
  <p><strong>Задать вопрос</strong></p>
  <p><a class="sfrfr-btn sfrfr-btn--primary" href="{$maxUrl}" target="_blank" rel="noopener noreferrer">Задать вопрос в MAX</a>
  <a class="sfrfr-btn sfrfr-btn--ghost" href="{$homeUrl}#zayavka">Оставить заявку</a>
  <a class="sfrfr-btn sfrfr-btn--ghost" href="{$homeUrl}#kak-rabotat">Начать проверку</a></p>
</div>
HTML;

$categories = [
    'ils' => 'ИЛС',
    'stazh' => 'Стаж',
    'dokumenty' => 'Документы',
    'podacha' => 'Подача',
    'rodstvenniki' => 'Для родственников',
    'usluga' => 'Услуга',
    'situacii' => 'Примеры ситуаций',
    'analitika' => 'Аналитика',
];

$catIds = [];
foreach ($categories as $slug => $name) {
    $term = get_term_by('slug', $slug, 'category');
    if ($term && !is_wp_error($term)) {
        $catIds[$slug] = (int) $term->term_id;
        continue;
    }
    $created = wp_insert_term($name, 'category', ['slug' => $slug, 'description' => $name]);
    if (is_wp_error($created)) {
        $term = get_term_by('name', $name, 'category');
        if ($term) {
            $catIds[$slug] = (int) $term->term_id;
            wp_update_term($term->term_id, 'category', ['slug' => $slug]);
        }
        continue;
    }
    $catIds[$slug] = (int) $created['term_id'];
}

function sfrfr_sit_upsert_post(array $args): int
{
    $existing = get_posts([
        'name' => $args['slug'],
        'post_type' => 'post',
        'post_status' => ['publish', 'draft', 'pending'],
        'numberposts' => 1,
        'fields' => 'ids',
    ]);
    $postarr = [
        'post_title' => $args['title'],
        'post_name' => $args['slug'],
        'post_status' => 'publish',
        'post_type' => 'post',
        'post_content' => $args['content'],
        'post_excerpt' => $args['excerpt'],
        'post_author' => 1,
    ];
    if ($existing) {
        $postarr['ID'] = (int) $existing[0];
        $id = wp_update_post($postarr, true);
    } else {
        $id = wp_insert_post($postarr, true);
    }
    if (is_wp_error($id)) {
        throw new RuntimeException($id->get_error_message());
    }
    $id = (int) $id;
    wp_set_post_categories($id, $args['category_ids']);
    update_post_meta($id, '_rank_math_title', $args['seo_title']);
    update_post_meta($id, '_rank_math_description', $args['seo_description']);
    update_post_meta($id, '_yoast_wpseo_title', $args['seo_title']);
    update_post_meta($id, '_yoast_wpseo_metadesc', $args['seo_description']);
    // ТЗ-18: массовые шаблонные ситуации не индексировать до редакционной
    // консолидации в самостоятельные экспертные pillar-материалы.
    update_post_meta($id, '_sfrfr_noindex', '1');
    return $id;
}

$seriesLinks = [];
foreach ($index as $item) {
    $seriesLinks[] = sprintf(
        '<li><a href="%s">%s</a></li>',
        esc_url(home_url('/blog/' . $item['slug'] . '/')),
        esc_html($item['title'])
    );
}
$seriesBlock = '<h2>Серия примеров и аналитики</h2><ul>' . implode("\n", array_slice($seriesLinks, 0, 8))
    . '</ul><p><a href="' . esc_url(home_url('/blog/rubrika/situacii/')) . '">Все примеры ситуаций</a> · '
    . '<a href="' . esc_url(home_url('/blog/rubrika/analitika/')) . '">Аналитика</a></p>';

$countSit = 0;
$countAn = 0;
foreach ($index as $item) {
    $path = rtrim($assets, '/\\') . DIRECTORY_SEPARATOR . $item['file'];
    if (!is_readable($path)) {
        throw new RuntimeException("Missing {$path}");
    }
    $body = (string) file_get_contents($path);
    $content = $body . "\n" . $ctaBlock . "\n" . $seriesBlock . "\n" . $disclaimer;

    $primary = $item['category'];
    $extra = ($item['kind'] === 'analytics') ? 'analitika' : 'situacii';
    $ids = [];
    foreach ([$extra, $primary] as $slug) {
        if (!empty($catIds[$slug])) {
            $ids[] = $catIds[$slug];
        }
    }
    $ids = array_values(array_unique($ids));
    if (!$ids) {
        throw new RuntimeException('No categories for ' . $item['slug']);
    }

    $id = sfrfr_sit_upsert_post([
        'slug' => $item['slug'],
        'title' => $item['title'],
        'content' => $content,
        'excerpt' => $item['excerpt'],
        'category_ids' => $ids,
        'seo_title' => $item['seo_title'],
        'seo_description' => $item['seo_description'],
    ]);
    if ($item['kind'] === 'analytics') {
        $countAn++;
        echo "ANALYTICS {$item['slug']}={$id}\n";
    } else {
        $countSit++;
        echo "SITUATION {$item['slug']}={$id}\n";
    }
}

// Permalink safety (не ломать статьи)
update_option('category_base', 'blog/rubrika');
update_option('permalink_structure', '/blog/%postname%/');
flush_rewrite_rules(false);

echo "OK situations={$countSit} analytics={$countAn}\n";
