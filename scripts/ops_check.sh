#!/usr/bin/env bash
# Мониторинг API (ТЗ-05): /health + локальный счётчик failed.
# Cron пример (каждые 5 мин):
#   */5 * * * * APP_DIR=/opt/sfrfr /opt/sfrfr/scripts/ops_check.sh >> /var/log/sfrfr-ops.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
cd "$APP_DIR"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "=== $(date -Is) ops_check ==="
python -m sfrfr ops-check-remote
python -m sfrfr ops-health --fail-on-alert
echo "ops_check OK"
