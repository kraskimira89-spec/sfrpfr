#!/usr/bin/env bash
# Логический бэкап Supabase Postgres → BACKUP_ROOT (том ВМ, регион РФ).
# Опционально: выгрузка в Object Storage через rclone, если есть ENV_FILE
# (S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET, S3_ENDPOINT, S3_REGION).
# db-01: параметры задаёт systemd-юнит sfrfr-supabase-backup.service.
set -euo pipefail
umask 077

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
BACKUP_ROOT="${BACKUP_ROOT:-/data/backups/supabase-staging}"
DUMP_USER="${DUMP_USER:-postgres}"
DATABASES="${DATABASES:-postgres}"
LOCAL_KEEP_DAYS="${LOCAL_KEEP_DAYS:-7}"
ENV_FILE="${ENV_FILE:-/etc/sfrfr-backup.env}"
S3_PREFIX="${S3_PREFIX:-supabase-staging}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${BACKUP_ROOT}/${STAMP}"

mkdir -p "$OUT_DIR"
cd "$COMPOSE_DIR"

for db in $DATABASES; do
  echo "dump ${db} → ${OUT_DIR}/${db}.dump"
  docker compose exec -T db pg_dump -U "$DUMP_USER" -d "$db" -Fc -f "/tmp/${db}.dump" </dev/null
  docker compose cp "db:/tmp/${db}.dump" "${OUT_DIR}/${db}.dump"
  docker compose exec -T db rm -f "/tmp/${db}.dump" </dev/null
done

echo "globals → ${OUT_DIR}/globals.sql"
docker compose exec -T db pg_dumpall -U "$DUMP_USER" --globals-only --no-role-passwords \
  </dev/null >"${OUT_DIR}/globals.sql"

# Схема-список таблиц для сверки
docker compose exec -T db psql -U "$DUMP_USER" -Atc \
  "select schemaname||'.'||relname||'='||n_live_tup
   from pg_stat_user_tables
   where schemaname in ('public','auth','storage','sfrfr_ops')
   order by 1" </dev/null >"${OUT_DIR}/rowcounts.txt" || true

(cd "$OUT_DIR" && sha256sum -- *.dump globals.sql | tee SHA256SUMS)
echo "OK backup ${OUT_DIR}"

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$LOCAL_KEEP_DAYS" \
  -exec rm -rf -- {} + -print

if [[ -r "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  export RCLONE_CONFIG_YC_TYPE=s3 RCLONE_CONFIG_YC_PROVIDER=Other \
    RCLONE_CONFIG_YC_ENDPOINT="$S3_ENDPOINT" RCLONE_CONFIG_YC_REGION="$S3_REGION" \
    RCLONE_CONFIG_YC_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" \
    RCLONE_CONFIG_YC_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY"
  DEST="yc:${S3_BUCKET}/${S3_PREFIX}/${STAMP}"
  echo "upload → ${DEST}"
  rclone copy "$OUT_DIR" "$DEST" --s3-no-check-bucket --config /dev/null
  rclone lsl "$DEST" --config /dev/null
  echo "OK upload ${DEST}"
else
  echo "WARN: ${ENV_FILE} not found, upload skipped"
fi
