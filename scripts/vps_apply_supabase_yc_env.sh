#!/usr/bin/env bash
# Применить Supabase YC env на VPS и пересобрать cabinet/admin.
set -euo pipefail

CUTOVER_ENV="${1:?cutover env file}"
APP_DIR="${APP_DIR:-/opt/sfrfr}"

set -a
# shellcheck disable=SC1090
source "$CUTOVER_ENV"
set +a

replace_env() {
  local file="$1" key="$2" value="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >>"$file"
  fi
}

replace_env "$APP_DIR/.env" "SUPABASE_URL" "$SUPABASE_URL"
replace_env "$APP_DIR/.env" "SUPABASE_ANON_KEY" "$SUPABASE_ANON_KEY"
replace_env "$APP_DIR/.env" "SUPABASE_SERVICE_ROLE_KEY" "$SUPABASE_SERVICE_ROLE_KEY"

replace_env "$APP_DIR/apps/cabinet/.env" "NEXT_PUBLIC_SUPABASE_URL" "$NEXT_PUBLIC_SUPABASE_URL"
replace_env "$APP_DIR/apps/cabinet/.env" "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY" "$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"
replace_env "$APP_DIR/apps/admin/.env" "NEXT_PUBLIC_SUPABASE_URL" "$NEXT_PUBLIC_SUPABASE_URL"
replace_env "$APP_DIR/apps/admin/.env" "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY" "$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"

# DATABASE_URL: FastAPI may use direct PG — point to disabled/local unused; prefer Supabase client.
# If old Cloud DATABASE_URL remains, API sqlAlchemy might still hit Cloud — neutralize to empty or YC.
if grep -q '^DATABASE_URL=' "$APP_DIR/.env"; then
  # Keep key but mark unused; service role REST is primary for many paths.
  # Safer: set to empty comment via placeholder localhost that fails closed if used.
  replace_env "$APP_DIR/.env" "DATABASE_URL" "postgresql+psycopg://postgres:unused@127.0.0.1:5432/postgres"
fi

echo "== rebuild cabinet/admin =="
sudo -u sfrfr bash -lc "
set -e
cd $APP_DIR/apps/cabinet && npm ci && npm run build
cd $APP_DIR/apps/admin && npm ci && npm run build
"

systemctl restart sfrfr-api sfrfr-cabinet sfrfr-admin
sleep 3
systemctl is-active sfrfr-api sfrfr-cabinet sfrfr-admin
grep -E '^SUPABASE_URL=' "$APP_DIR/.env"
grep -E '^NEXT_PUBLIC_SUPABASE_URL=' "$APP_DIR/apps/cabinet/.env" "$APP_DIR/apps/admin/.env"
curl -sS -o /dev/null -w "api_health=%{http_code}\n" http://127.0.0.1:8011/health || true
echo "OK apply"
