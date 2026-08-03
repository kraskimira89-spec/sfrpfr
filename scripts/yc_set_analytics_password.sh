#!/usr/bin/env bash
# Установить пароль analytics_transformer на self-host Postgres (внутри compose).
# Usage on YC VM: DBT_PASSWORD=... bash yc_set_analytics_password.sh
set -euo pipefail
cd /opt/sfrfr-supabase/supabase/docker
: "${DBT_PASSWORD:?DBT_PASSWORD required}"
python3 - <<'PY' | docker compose exec -T db psql -U postgres -d postgres -v ON_ERROR_STOP=1
import os
pw = os.environ["DBT_PASSWORD"]
tag = "pw"
while tag in pw:
    tag += "x"
print("ALTER ROLE analytics_transformer PASSWORD $" + tag + "$" + pw + "$" + tag + "$;")
PY
docker compose exec -T db psql -U postgres -d postgres -Atc \
  "SELECT 'role_ok='||rolcanlogin FROM pg_roles WHERE rolname='analytics_transformer';"
echo OK password set
