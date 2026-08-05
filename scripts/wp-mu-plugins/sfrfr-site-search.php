<?php
/**
 * Plugin Name: SFRFR Site Search
 * Description: Поле поиска по сайту в шапке (меню primary) и русская форма результатов.
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
 * Поиск: страницы + записи блога; без вложений.
 *
 * @param WP_Query $query
 */
add_action('pre_get_posts', static function ($query): void {
    if (is_admin() || !$query instanceof WP_Query || !$query->is_main_query() || !$query->is_search()) {
        return;
    }
    $query->set('post_type', ['post', 'page']);
    $query->set('post_status', 'publish');
});
