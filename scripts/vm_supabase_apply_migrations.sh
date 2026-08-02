#!/usr/bin/env bash
# Применить supabase/migrations/*.sql к self-host staging (через docker exec db).
# Ожидает каталог /tmp/sfrfr-migrations на ВМ (скопировать scp).
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
MIG_DIR="${MIG_DIR:-/tmp/sfrfr-migrations}"
SEED="${SEED:-/tmp/sfrfr-seed-synthetic.sql}"

cd "$COMPOSE_DIR"

docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 <<'SQL'
create schema if not exists sfrfr_ops;
create table if not exists sfrfr_ops.schema_migrations (
  filename text primary key,
  applied_at timestamptz not null default now()
);
SQL

shopt -s nullglob
files=("$MIG_DIR"/*.sql)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "FAIL: no migrations in $MIG_DIR" >&2
  exit 1
fi

for f in "${files[@]}"; do
  base=$(basename "$f")
  applied=$(docker compose exec -T db psql -U postgres -tAc \
    "select 1 from sfrfr_ops.schema_migrations where filename='${base}'")
  if [[ "$(echo "$applied" | tr -d '[:space:]')" == "1" ]]; then
    echo "skip $base"
    continue
  fi
  echo "apply $base"
  docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 <"$f"
  docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 \
    -c "insert into sfrfr_ops.schema_migrations(filename) values ('${base}');"
done

if [[ -f "$SEED" ]]; then
  echo "seed synthetic"
  docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 <"$SEED"
fi

echo "OK migrations applied"
docker compose exec -T db psql -U postgres -c \
  "select filename, applied_at from sfrfr_ops.schema_migrations order by applied_at;"
