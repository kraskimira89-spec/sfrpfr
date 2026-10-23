#!/usr/bin/env bash
# Восстановить weekly cron UpdraftPlus, если события updraft_backup* пропали.
# Пустой updraft_service="" ломает methods/"".php — нормализуем в none.
#
#   bash /opt/sfrfr/scripts/wp_updraft_ensure_schedule.sh
# Cron (ежедневно 03:50, до синка на Диск пн 04:30):
#   50 3 * * * root APP_DIR=/opt/sfrfr bash /opt/sfrfr/scripts/wp_updraft_ensure_schedule.sh >>/var/log/sfrfr-wp-updraft-ensure.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
SITE_DIR="${SITE_DIR:-/var/www/proverkastaza}"

if ! command -v wp >/dev/null 2>&1; then
  echo "ERR: wp-cli not found" >&2
  exit 1
fi
if [[ ! -d "$SITE_DIR" ]]; then
  echo "ERR: no site dir $SITE_DIR" >&2
  exit 1
fi

wp --path="$SITE_DIR" --allow-root eval '
$svc = get_option("updraft_service");
if ($svc === "" || $svc === false || $svc === null || $svc === array("")) {
  update_option("updraft_service", "none");
  echo "fixed updraft_service -> none\n";
} else {
  echo "updraft_service ok\n";
}
$u = $GLOBALS["updraftplus"];
$u->schedule_backup(get_option("updraft_interval") ?: "weekly");
$u->schedule_backup_database(get_option("updraft_interval_database") ?: "weekly");
$has_files = (bool) wp_next_scheduled("updraft_backup");
$has_db = (bool) wp_next_scheduled("updraft_backup_database");
echo "updraft_backup=" . ($has_files ? "yes" : "no") . "\n";
echo "updraft_backup_database=" . ($has_db ? "yes" : "no") . "\n";
if (!$has_files || !$has_db) {
  fwrite(STDERR, "ERR: schedule still missing after ensure\n");
  exit(1);
}
echo "ensure ok\n";
'
