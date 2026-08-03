#!/usr/bin/env bash
# Auth redirect allow-list for self-host GoTrue (cutover).
set -euo pipefail
cd /opt/sfrfr-supabase/supabase/docker
cp -a .env ".env.bak.redirects.$(date +%Y%m%d%H%M%S)"
REDIRS='https://cabinet.proverkastaza.ru/**,https://cabinet.proverkastaza.ru/?mode=recover,https://admin.proverkastaza.ru/**'
if grep -q '^ADDITIONAL_REDIRECT_URLS=' .env; then
  sed -i "s|^ADDITIONAL_REDIRECT_URLS=.*|ADDITIONAL_REDIRECT_URLS=${REDIRS}|" .env
else
  printf 'ADDITIONAL_REDIRECT_URLS=%s\n' "$REDIRS" >> .env
fi
grep -E '^(SITE_URL|ADDITIONAL_REDIRECT_URLS)=' .env
docker compose up -d auth --force-recreate
sleep 5
docker compose ps auth --format '{{.Name}} {{.Status}}'
ANON="$(grep '^ANON_KEY=' .env | cut -d= -f2-)"
curl -sS -o /dev/null -w 'auth_health=%{http_code}\n' \
  -H "apikey: ${ANON}" -H "Authorization: Bearer ${ANON}" \
  https://supabase.proverkastaza.ru/auth/v1/health
echo OK
