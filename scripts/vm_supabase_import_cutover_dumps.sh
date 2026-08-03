#!/usr/bin/env bash
# Импорт secrets/cutover-dumps/*.copy в self-host Postgres (на ВМ).
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
DUMP_DIR="${DUMP_DIR:-/tmp/cutover-dumps}"

cd "$COMPOSE_DIR"

docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
TRUNCATE TABLE public.clients CASCADE;
TRUNCATE TABLE auth.refresh_tokens CASCADE;
TRUNCATE TABLE auth.sessions CASCADE;
TRUNCATE TABLE auth.identities CASCADE;
TRUNCATE TABLE auth.users CASCADE;
COMMIT;
SQL

while IFS=$'\t' read -r fq fname nrows; do
  [[ -z "${fq:-}" ]] && continue
  path="$DUMP_DIR/$fname"
  if [[ ! -f "$path" ]]; then
    echo "MISSING $path" >&2
    exit 1
  fi
  echo "import $fq ($nrows) <- $fname"
  # disable triggers for FK order flexibility where needed
  docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 \
    -c "COPY $fq FROM STDIN" <"$path"
done <"$DUMP_DIR/manifest.tsv"

echo "=== counts ==="
docker compose exec -T db psql -U postgres -c \
  "select 'clients' t, count(*) c from public.clients
   union all select 'cases', count(*) from public.cases
   union all select 'documents', count(*) from public.documents
   union all select 'auth.users', count(*) from auth.users;"
echo "OK import"
