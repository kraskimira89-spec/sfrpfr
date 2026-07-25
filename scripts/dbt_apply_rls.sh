#!/usr/bin/env bash
# Включает RLS и снимает права anon/authenticated с витрин analytics.*.
# Вызывается после dbt build; не использует dbt post-hook (зависания на COMMIT).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SFRFR_ENV_FILE:-$ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${DBT_HOST:?DBT_HOST must be set}"
: "${DBT_PASSWORD:?DBT_PASSWORD must be set}"

DBT_PORT="${DBT_PORT:-5432}"
DBT_USER="${DBT_USER:-analytics_transformer}"
DBT_DBNAME="${DBT_DBNAME:-postgres}"

export PGPASSWORD="$DBT_PASSWORD"
CONN="host=${DBT_HOST} port=${DBT_PORT} user=${DBT_USER} dbname=${DBT_DBNAME} sslmode=require connect_timeout=30"

psql "$CONN" -v ON_ERROR_STOP=1 <<'SQL'
do $$
declare
  r record;
begin
  for r in
    select format('%I.%I', n.nspname, c.relname) as fqname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'analytics'
      and c.relkind = 'r'
      and pg_get_userbyid(c.relowner) = current_user
  loop
    execute format('alter table %s enable row level security', r.fqname);
    execute format('revoke all on %s from public, anon, authenticated', r.fqname);
  end loop;
end
$$;
SQL
