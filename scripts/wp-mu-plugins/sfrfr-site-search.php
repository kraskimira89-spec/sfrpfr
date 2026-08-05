<?php
/**
 * Plugin Name: SFRFR Site Search
 * Description: Поиск в шапке + лента результатов с подсветкой и статистикой упоминаний.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * HTML формы поиска.
 */
function sfrfr_site_search_form_html(string $variant = 'header'): string
{
    $action = esc_url(home_url('/'));
    $q = get_search_query();
    $id = $variant === 'header' ? 'sfrfr-search-header' : 'sfrfr-search-page';
    $value = $q !== '' ? ' value="' . esc_attr($q) . '"' : '';

    return <<<HTML
<form class="sfrfr-site-search sfrfr-site-search--{$variant}" role="search" method="get" action="{$action}">
  <label class="sfrfr-site-search__label" for="{$id}">Поиск по сайту</label>
  <div class="sfrfr-site-search__field">
    <input class="sfrfr-site-search__input" type="search" id="{$id}" name="s"{$value} placeholder="Поиск…" autocomplete="off" enterkeyhint="search">
    <button class="sfrfr-site-search__submit" type="submit">Найти</button>
  </div>
</form>
HTML;
}

/**
 * Стандартный get_search_form → наша разметка.
 */
add_filter('get_search_form', static function (): string {
    return sfrfr_site_search_form_html('page');
});

/**
 * Компактная форма в конце primary-меню (desktop + mobile drawer).
 *
 * @param string   $items
 * @param stdClass $args
 */
add_filter('wp_nav_menu_items', static function (string $items, $args): string {
    $location = is_object($args) ? (string) ($args->theme_location ?? '') : '';
    if ($location !== 'primary' && $location !== 'mobile_menu') {
        return $items;
    }
    if (str_contains($items, 'sfrfr-menu-search')) {
        return $items;
    }
    $form = sfrfr_site_search_form_html('header');
    return $items . '<li class="menu-item sfrfr-menu-search" role="none">' . $form . '</li>';
}, 20, 2);

/**
 * Допустимые размеры страницы результатов поиска.
 *
 * @return list<int>
 */
function sfrfr_search_per_page_choices(): array
{
    return [10, 20, 50];
}

/**
 * Сколько результатов на странице (по умолчанию 20).
 */
function sfrfr_search_per_page(): int
{
    $raw = 20;
    if (isset($_GET['per_page'])) {
        $raw = (int) $_GET['per_page'];
    } elseif (isset($_GET['n'])) {
        // совместимость со старым параметром
        $raw = (int) $_GET['n'];
    }
    $allowed = sfrfr_search_per_page_choices();
    return in_array($raw, $allowed, true) ? $raw : 20;
}

/**
 * Поиск: страницы + записи блога; без вложений; размер страницы.
 *
 * @param WP_Query $query
 */
add_action('pre_get_posts', static function ($query): void {
    if (is_admin() || !$query instanceof WP_Query || !$query->is_main_query() || !$query->is_search()) {
        return;
    }
    $query->set('post_type', ['post', 'page']);
    $query->set('post_status', 'publish');
    $query->set('posts_per_page', sfrfr_search_per_page());
}, 99);

/**
 * Astra задаёт posts_per_page на parse_tax_query — перебиваем фильтром.
 *
 * @param int $limit
 */
add_filter('astra_blog_post_per_page', static function ($limit) {
    if (is_admin()) {
        return $limit;
    }
    if (is_search() || (isset($_GET['s']) && is_string($_GET['s']) && $_GET['s'] !== '')) {
        return sfrfr_search_per_page();
    }
    return $limit;
}, 20);

add_action('parse_tax_query', static function ($query): void {
    if (is_admin() || !$query instanceof WP_Query || !$query->is_main_query() || !$query->is_search()) {
        return;
    }
    $query->set('posts_per_page', sfrfr_search_per_page());
}, 20);

/**
 * Сохранить параметр per_page в ссылках пагинации поиска.
 */
add_filter('get_pagenum_link', static function (string $url): string {
    if (!is_search()) {
        return $url;
    }
    $n = sfrfr_search_per_page();
    if ($n === 20) {
        return $url;
    }
    return add_query_arg('per_page', $n, $url);
});

/**
 * Склонение слова.
 *
 * @param array{1:string,2:string,5:string} $forms формы: 1, 2-4, 5+
 */
function sfrfr_search_plural(int $n, array $forms): string
{
    $n = abs($n) % 100;
    $n1 = $n % 10;
    if ($n > 10 && $n < 20) {
        return $forms[5];
    }
    if ($n1 > 1 && $n1 < 5) {
        return $forms[2];
    }
    if ($n1 === 1) {
        return $forms[1];
    }
    return $forms[5];
}

function sfrfr_search_materials_word(int $n): string
{
    return sfrfr_search_plural($n, [1 => 'статья', 2 => 'статьи', 5 => 'статей']);
}

function sfrfr_search_mentions_word(int $n): string
{
    return sfrfr_search_plural($n, [1 => 'упоминание', 2 => 'упоминания', 5 => 'упоминаний']);
}

/**
 * Число вхождений needle в тексте (без учёта регистра).
 */
function sfrfr_search_count_mentions(string $haystack, string $needle): int
{
    $needle = trim($needle);
    if ($needle === '' || $haystack === '') {
        return 0;
    }
    $pattern = '/' . preg_quote($needle, '/') . '/iu';
    if (@preg_match_all($pattern, $haystack, $m) === false) {
        return 0;
    }
    return count($m[0] ?? []);
}

/**
 * Текст поста для поиска упоминаний.
 */
function sfrfr_search_post_plain(int $postId): string
{
    $title = (string) get_post_field('post_title', $postId);
    $content = (string) get_post_field('post_content', $postId);
    $excerpt = (string) get_post_field('post_excerpt', $postId);
    $text = $title . "\n" . $excerpt . "\n" . wp_strip_all_tags($content);
    $text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $text = preg_replace('/\s+/u', ' ', $text) ?? $text;
    return trim($text);
}

/**
 * Фрагмент с подсветкой первого (и остальных в окне) вхождения.
 */
function sfrfr_search_highlighted_snippet(string $plain, string $needle, int $radius = 100): string
{
    $needle = trim($needle);
    if ($plain === '') {
        return '';
    }
    if ($needle === '') {
        $cut = function_exists('mb_substr') ? mb_substr($plain, 0, 200) : substr($plain, 0, 200);
        return esc_html($cut);
    }

    $pos = function_exists('mb_stripos') ? mb_stripos($plain, $needle) : stripos($plain, $needle);
    $lenPlain = function_exists('mb_strlen') ? mb_strlen($plain) : strlen($plain);
    $lenNeedle = function_exists('mb_strlen') ? mb_strlen($needle) : strlen($needle);

    if ($pos === false) {
        $cut = function_exists('mb_substr') ? mb_substr($plain, 0, 200) : substr($plain, 0, 200);
        $suffix = $lenPlain > 200 ? '…' : '';
        return esc_html($cut) . $suffix;
    }

    $start = max(0, (int) $pos - $radius);
    $length = $radius * 2 + (int) $lenNeedle;
    $excerpt = function_exists('mb_substr')
        ? mb_substr($plain, $start, $length)
        : substr($plain, $start, $length);

    $prefix = $start > 0 ? '…' : '';
    $endPos = $start + (function_exists('mb_strlen') ? mb_strlen($excerpt) : strlen($excerpt));
    $suffix = $endPos < $lenPlain ? '…' : '';

    $safe = esc_html($excerpt);
    $pattern = '/(' . preg_quote($needle, '/') . ')/iu';
    $highlighted = preg_replace($pattern, '<mark class="sfrfr-search-hit">$1</mark>', $safe);
    if (!is_string($highlighted)) {
        $highlighted = $safe;
    }

    return $prefix . $highlighted . $suffix;
}

/**
 * Заголовок с подсветкой запроса.
 */
function sfrfr_search_highlighted_title(string $title, string $needle): string
{
    $safe = esc_html($title);
    $needle = trim($needle);
    if ($needle === '') {
        return $safe;
    }
    $pattern = '/(' . preg_quote($needle, '/') . ')/iu';
    $out = preg_replace($pattern, '<mark class="sfrfr-search-hit">$1</mark>', $safe);
    return is_string($out) ? $out : $safe;
}

/**
 * @return array{articles:int,mentions:int}
 */
function sfrfr_search_compute_stats(string $term): array
{
    $term = trim($term);
    $articles = 0;
    $mentions = 0;
    if ($term === '') {
        return ['articles' => 0, 'mentions' => 0];
    }

    $ids = get_posts([
        's' => $term,
        'post_type' => ['post', 'page'],
        'post_status' => 'publish',
        'fields' => 'ids',
        'posts_per_page' => 300,
        'no_found_rows' => true,
        'suppress_filters' => false,
    ]);
    $articles = count($ids);
    foreach ($ids as $id) {
        $mentions += sfrfr_search_count_mentions(sfrfr_search_post_plain((int) $id), $term);
    }

    return ['articles' => $articles, 'mentions' => $mentions];
}

/**
 * @return array{articles:int,mentions:int}
 */
function sfrfr_search_stats(): array
{
    global $wp_query;
    if (isset($wp_query->sfrfr_search_stats) && is_array($wp_query->sfrfr_search_stats)) {
        return $wp_query->sfrfr_search_stats;
    }
    $stats = sfrfr_search_compute_stats(get_search_query(false));
    if ($wp_query instanceof WP_Query) {
        $wp_query->sfrfr_search_stats = $stats;
    }
    return $stats;
}

function sfrfr_search_stats_title_html(): string
{
    $stats = sfrfr_search_stats();
    $query = get_search_query(false);
    $mentions = (int) $stats['mentions'];
    $articles = (int) $stats['articles'];
    return sprintf(
        'Найдено %d %s · %d %s по запросу «%s»',
        $mentions,
        sfrfr_search_mentions_word($mentions),
        $articles,
        sfrfr_search_materials_word($articles),
        esc_html($query)
    );
}

/**
 * Заголовок поиска Astra: упоминания + статьи.
 *
 * @param string $title
 */
add_filter('astra_the_search_page_title', static function (string $title): string {
    return sfrfr_search_stats_title_html();
}, 20);

/**
 * @param string $title
 */
add_filter('get_the_archive_title', static function (string $title): string {
    if (!is_search()) {
        return $title;
    }
    return sfrfr_search_stats_title_html();
}, 20);

/**
 * Подменить цикл Astra на ленту с контекстом.
 */
add_action('wp', static function (): void {
    if (is_admin() || !is_search()) {
        return;
    }
    remove_all_actions('astra_content_loop');
    add_action('astra_content_loop', 'sfrfr_render_search_feed');
}, 20);

/**
 * Выбор «показывать по N» над лентой.
 */
function sfrfr_render_search_per_page_control(): void
{
    $current = sfrfr_search_per_page();
    $term = get_search_query(false);
    $action = esc_url(home_url('/'));

    echo '<form class="sfrfr-search-perpage" method="get" action="' . $action . '">';
    echo '<input type="hidden" name="s" value="' . esc_attr($term) . '">';
    echo '<label for="sfrfr-search-per-page">Показывать по</label> ';
    echo '<select id="sfrfr-search-per-page" name="per_page" onchange="this.form.submit()">';
    foreach (sfrfr_search_per_page_choices() as $n) {
        printf(
            '<option value="%d"%s>%d</option>',
            $n,
            selected($current, $n, false),
            $n
        );
    }
    echo '</select>';
    echo ' <span class="sfrfr-search-perpage__hint">на странице</span>';
    echo '</form>';
}

/**
 * Лента результатов поиска.
 */
function sfrfr_render_search_feed(): void
{
    sfrfr_render_search_per_page_control();

    if (!have_posts()) {
        echo '<div class="sfrfr-search-feed sfrfr-search-feed--empty">';
        echo '<p>По вашему запросу ничего не найдено. Попробуйте другие слова или откройте <a href="' . esc_url(home_url('/blog/')) . '">раздел статей</a>.</p>';
        echo '</div>';
        return;
    }

    $term = get_search_query(false);
    echo '<div class="sfrfr-search-feed" role="list">';

    $i = 0;
    while (have_posts()) {
        the_post();
        $postId = (int) get_the_ID();
        $plain = sfrfr_search_post_plain($postId);
        $inPost = sfrfr_search_count_mentions($plain, $term);
        $snippet = sfrfr_search_highlighted_snippet($plain, $term);
        $titleHtml = sfrfr_search_highlighted_title(get_the_title(), $term);
        $url = get_permalink();
        $date = get_the_date('d.m.Y');
        $side = ($i % 2 === 0) ? 'left' : 'right';
        $i++;

        echo '<article class="sfrfr-search-item sfrfr-search-item--' . esc_attr($side) . '" role="listitem">';
        echo '<h2 class="sfrfr-search-item__title"><a href="' . esc_url($url ?: '#') . '">' . $titleHtml . '</a></h2>';
        if ($snippet !== '') {
            echo '<p class="sfrfr-search-item__snippet">' . $snippet . '</p>';
        }
        echo '<p class="sfrfr-search-item__meta">';
        echo esc_html((string) $inPost) . ' ' . esc_html(sfrfr_search_mentions_word($inPost));
        if ($date) {
            echo ' · ' . esc_html($date);
        }
        if (get_post_type() === 'page') {
            echo ' · страница';
        }
        echo '</p>';
        echo '</article>';
    }

    echo '</div>';
}
