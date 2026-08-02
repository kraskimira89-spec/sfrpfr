#!/usr/bin/env bash
# Логический бэкап staging Postgres → /data/backups (том ВМ, регион РФ).
# Опционально: AWSCLI/yc к бакету sfrfr-staging-backup-* (если настроено).
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
BACKUP_ROOT="${BACKUP_ROOT:-/data/backups/supabase-staging}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${BACKUP_ROOT}/${STAMP}"

mkdir -p "$OUT_DIR"
cd "$COMPOSE_DIR"

echo "dump → ${OUT_DIR}/postgres.dump"
docker compose exec -T db pg_dump -U postgres -Fc -f /tmp/postgres.dump
docker compose cp db:/tmp/postgres.dump "${OUT_DIR}/postgres.dump"
docker compose exec -T db rm -f /tmp/postgres.dump

# Схема-список таблиц для сверки
docker compose exec -T db psql -U postgres -Atc \
  "select schemaname||'.'||relname||'='||n_live_tup
   from pg_stat_user_tables
   where schemaname in ('public','auth','storage','sfrfr_ops')
   order by 1" > "${OUT_DIR}/rowcounts.txt" || true

sha256sum "${OUT_DIR}/postgres.dump" | tee "${OUT_DIR}/postgres.dump.sha256"
echo "OK backup ${OUT_DIR}"

# Опциональная выгрузка в Object Storage (если yc настроен на ВМ)
if command -v yc >/dev/null 2>&1 && [[ -n "${YC_BACKUP_BUCKET:-}" ]]; then
  yc storage s3api put-object \
    --bucket "$YC_BACKUP_BUCKET" \
    --key "supabase-staging/${STAMP}/postgres.dump" \
    --body "${OUT_DIR}/postgres.dump" || echo "WARN: upload to bucket failed"
fi
