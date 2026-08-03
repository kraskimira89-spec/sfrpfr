#!/usr/bin/env bash
# Импорт /tmp/cutover-dumps/cloud_data.sql в self-host Postgres.
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
SQL="${SQL:-/tmp/cutover-dumps/cloud_data.sql}"

cd "$COMPOSE_DIR"
test -f "$SQL"

echo "import $SQL"
docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 <"$SQL"

echo "=== counts ==="
docker compose exec -T db psql -U postgres -c \
  "select 'clients' t, count(*) c from public.clients
   union all select 'cases', count(*) from public.cases
   union all select 'documents', count(*) from public.documents
   union all select 'auth.users', count(*) from auth.users;"
echo "OK import"
