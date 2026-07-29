<?php
/**
 * Plugin Name: SFRFR Internal Stats
 * Description: Обезличенная серверная агрегация (просмотры, форма, ошибки) без mc.yandex.ru и без IP.
 */

if (!defined('ABSPATH')) {
    exit;
}

/** @return string */
function sfrfr_stats_table(): string
{
    global $wpdb;
    return $wpdb->prefix . 'sfrfr_internal_stats';
}

function sfrfr_stats_maybe_install(): void
{
    global $wpdb;
    $table = sfrfr_stats_table();
    $ver_key = 'sfrfr_internal_stats_db_v';
    if ((string) get_option($ver_key, '') === '1') {
        return;
    }
    $charset = $wpdb->get_charset_collate();
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta(
        "CREATE TABLE {$table} (
            stat_date date NOT NULL,
            event_code varchar(32) NOT NULL,
            path_key varchar(160) NOT NULL DEFAULT '',
            cnt bigint unsigned NOT NULL DEFAULT 0,
            PRIMARY KEY  (stat_date, event_code, path_key),
            KEY event_date (event_code, stat_date)
        ) {$charset};"
    );
    update_option($ver_key, '1', true);
}

add_action('init', 'sfrfr_stats_maybe_install', 1);

/**
 * @param string $event page_view|lead_ok|form_error|http_404|consent_allow|consent_deny|tech_error
 * @param string $path_key уже очищенный path или ''
 */
function sfrfr_stats_bump(string $event, string $path_key = ''): void
{
    global $wpdb;
    $event = preg_replace('/[^a-z0-9_]/', '', strtolower($event)) ?? '';
    if ($event === '' || strlen($event) > 32) {
        return;
    }
    $path_key = sfrfr_stats_normalize_path($path_key);
    $table = sfrfr_stats_table();
    $date = gmdate('Y-m-d');
    // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared -- table name fixed
    $wpdb->query(
        $wpdb->prepare(
            "INSERT INTO {$table} (stat_date, event_code, path_key, cnt)
             VALUES (%s, %s, %s, 1)
             ON DUPLICATE KEY UPDATE cnt = cnt + 1",
            $date,
            $event,
            $path_key
        )
    );
}

function sfrfr_stats_normalize_path(string $raw): string
{
    $raw = trim($raw);
    if ($raw === '') {
        $uri = isset($_SERVER['REQUEST_URI']) ? (string) $_SERVER['REQUEST_URI'] : '/';
        $path = (string) (parse_url($uri, PHP_URL_PATH) ?: '/');
    } else {
        $path = (string) (parse_url($raw, PHP_URL_PATH) ?: $raw);
    }
    $path = '/' . ltrim($path, '/');
    if (strlen($path) > 160) {
        $path = substr($path, 0, 160);
    }
    // только безопасный алфавит пути
    $path = preg_replace('#[^a-zA-Z0-9/_\-.]#', '', $path) ?? '/';
    return $path === '' ? '/' : $path;
}

function sfrfr_stats_is_bot_ua(): bool
{
    $ua = isset($_SERVER['HTTP_USER_AGENT']) ? strtolower((string) $_SERVER['HTTP_USER_AGENT']) : '';
    if ($ua === '') {
        return true;
    }
    foreach (['bot', 'spider', 'crawl', 'slurp', 'facebookexternalhit', 'preview'] as $needle) {
        if (str_contains($ua, $needle)) {
            return true;
        }
    }
    return false;
}

add_action('template_redirect', static function (): void {
    if (is_admin() || wp_doing_ajax() || wp_doing_cron() || (defined('REST_REQUEST') && REST_REQUEST)) {
        return;
    }
    if (sfrfr_stats_is_bot_ua()) {
        return;
    }
    if (is_404()) {
        sfrfr_stats_bump('http_404');
        return;
    }
    sfrfr_stats_bump('page_view');
}, 0);

add_action('wpforms_process_complete', static function ($fields, $entry, $form_data, $entry_id): void {
    unset($fields, $entry, $form_data, $entry_id);
    sfrfr_stats_bump('lead_ok', '/#zayavka');
}, 10, 4);

add_action('wpforms_process', static function ($fields, $entry, $form_data): void {
    unset($fields, $entry);
    if (!empty($form_data['errors'])) {
        sfrfr_stats_bump('form_error', '/#zayavka');
    }
}, 1000, 3);

add_action('wpforms_ajax_submit_error', static function (): void {
    sfrfr_stats_bump('form_error', '/#zayavka');
}, 10, 0);

/** Beacon: только код события, без тела формы / IP в ответе. */
add_action('wp_ajax_nopriv_sfrfr_stat_hit', 'sfrfr_stats_ajax_hit');
add_action('wp_ajax_sfrfr_stat_hit', 'sfrfr_stats_ajax_hit');

function sfrfr_stats_ajax_hit(): void
{
    $event = isset($_REQUEST['e']) ? (string) $_REQUEST['e'] : '';
    $allowed = [
        'consent_allow' => true,
        'consent_deny' => true,
        'tech_error' => true,
    ];
    if (!isset($allowed[$event])) {
        status_header(400);
        wp_die('', '', ['response' => 400]);
    }
    sfrfr_stats_bump($event);
    status_header(204);
    wp_die('', '', ['response' => 204]);
}
