#!/usr/bin/env bash
# Restore-drill: восстановить последний dump в БД restore_drill (не трогает postgres).
# Критерий фазы 1 ТЗ-15: dump читается, таблицы public.* на месте.
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
BACKUP_ROOT="${BACKUP_ROOT:-/data/backups/supabase-staging}"
DRILL_DB="${DRILL_DB:-restore_drill}"

cd "$COMPOSE_DIR"

LATEST=$(ls -1dt "${BACKUP_ROOT}"/*/postgres.dump 2>/dev/null | head -1 || true)
if [[ -z "${LATEST}" ]]; then
  echo "FAIL: no dump under ${BACKUP_ROOT}" >&2
  exit 1
fi
echo "using ${LATEST}"

docker compose cp "${LATEST}" db:/tmp/restore_drill.dump

docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 <<SQL
select pg_terminate_backend(pid) from pg_stat_activity
  where datname = '${DRILL_DB}' and pid <> pg_backend_pid();
drop database if exists ${DRILL_DB};
create database ${DRILL_DB};
SQL

# -Fc dump → pg_restore (часть объектов auth/storage может ругаться — допускаем)
set +e
docker compose exec -T db pg_restore -U postgres -d "${DRILL_DB}" --no-owner --verbose \
  /tmp/restore_drill.dump 2>&1 | tail -n 40
RC=${PIPESTATUS[0]}
set -e

docker compose exec -T db rm -f /tmp/restore_drill.dump

COUNT=$(docker compose exec -T db psql -U postgres -d "${DRILL_DB}" -Atc \
  "select count(*) from information_schema.tables where table_schema='public';")
echo "public_tables=${COUNT}"

if [[ "${COUNT}" -lt 1 ]]; then
  echo "FAIL: restore_drill has no public tables" >&2
  exit 1
fi

echo "OK restore_drill (pg_restore_exit=${RC}; public_tables=${COUNT})"
echo "HINT: drop database ${DRILL_DB} after review if disk tight"
