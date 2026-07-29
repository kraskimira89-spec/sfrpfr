<?php
/**
 * Отчёт по внутренней обезличенной статистике.
 * wp eval-file scripts/wp_internal_stats_report.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

global $wpdb;
$table = $wpdb->prefix . 'sfrfr_internal_stats';
$exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $table));
if (!$exists) {
    echo "NO_TABLE\n";
    exit(0);
}

$days = 14;
$rows = $wpdb->get_results(
    $wpdb->prepare(
        "SELECT stat_date, event_code, SUM(cnt) AS total
         FROM {$table}
         WHERE stat_date >= DATE_SUB(UTC_DATE(), INTERVAL %d DAY)
         GROUP BY stat_date, event_code
         ORDER BY stat_date DESC, event_code ASC",
        $days
    ),
    ARRAY_A
);

echo "internal_stats last {$days}d (UTC, no IP/PII)\n";
if (!$rows) {
    echo "(empty)\n";
    exit(0);
}
foreach ($rows as $r) {
    echo $r['stat_date'] . "\t" . $r['event_code'] . "\t" . $r['total'] . "\n";
}
