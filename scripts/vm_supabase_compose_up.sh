#!/usr/bin/env bash
set -euo pipefail
cd /opt/sfrfr-supabase/supabase/docker
if [ ! -f .env ]; then
  echo "missing .env — abort"
  exit 1
fi
docker compose pull
docker compose up -d
sleep 5
docker compose ps
