#!/usr/bin/env bash
# Переключить DATABASE_URL + DBT_* на self-host Postgres (YC).
# Usage on VPS:
#   YC_PG_HOST=... YC_PG_PASSWORD=... DBT_PASSWORD=... sudo -E bash scripts/vps_switch_db_to_yc.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
ENV_FILE="${APP_DIR}/.env"
YC_PG_HOST="${YC_PG_HOST:?YC_PG_HOST required}"
YC_PG_PORT="${YC_PG_PORT:-5433}"
YC_PG_DB="${YC_PG_DB:-postgres}"
YC_PG_PASSWORD="${YC_PG_PASSWORD:?YC_PG_PASSWORD required}"
DBT_PASSWORD="${DBT_PASSWORD:?DBT_PASSWORD required}"
DBT_USER="${DBT_USER:-analytics_transformer}"

replace_env() {
  local file="$1" key="$2" value="$3"
  python3 - "$file" "$key" "$value" <<'PY'
import sys
from pathlib import Path
path, key, value = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
lines = path.read_text().splitlines()
out, found = [], False
for line in lines:
    if line.startswith(key + "="):
        out.append(f"{key}={value}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n")
PY
}

cp -a "$ENV_FILE" "${ENV_FILE}.bak.db_yc.$(date +%Y%m%d%H%M%S)"

DATABASE_URL="postgresql+psycopg://postgres:${YC_PG_PASSWORD}@${YC_PG_HOST}:${YC_PG_PORT}/${YC_PG_DB}?sslmode=disable"

replace_env "$ENV_FILE" "DATABASE_URL" "$DATABASE_URL"
replace_env "$ENV_FILE" "DBT_HOST" "$YC_PG_HOST"
replace_env "$ENV_FILE" "DBT_PORT" "$YC_PG_PORT"
replace_env "$ENV_FILE" "DBT_USER" "$DBT_USER"
replace_env "$ENV_FILE" "DBT_PASSWORD" "$DBT_PASSWORD"
replace_env "$ENV_FILE" "DBT_DBNAME" "$YC_PG_DB"
replace_env "$ENV_FILE" "DBT_SSLMODE" "disable"

PROFILES="${APP_DIR}/analytics/profiles.yml"
if [[ -f "$PROFILES" ]]; then
  python3 - "$PROFILES" <<'PY'
import re
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text()
repl = 'sslmode: "{{ env_var(\'DBT_SSLMODE\', \'disable\') }}"'
if re.search(r"^\s*sslmode:\s*", text, flags=re.M):
    text = re.sub(r"^\s*sslmode:\s*\S+.*$", f"      {repl}", text, count=1, flags=re.M)
else:
    text = text.rstrip() + f"\n      {repl}\n"
p.write_text(text)
print("profiles.yml: sslmode -> DBT_SSLMODE")
PY
fi

echo "== smoke psql postgres =="
PGPASSWORD="$YC_PG_PASSWORD" psql \
  "host=${YC_PG_HOST} port=${YC_PG_PORT} dbname=${YC_PG_DB} user=postgres sslmode=disable connect_timeout=10" \
  -Atc "select 'pg_ok='||count(*) from public.clients;"

echo "== smoke psql analytics_transformer =="
PGPASSWORD="$DBT_PASSWORD" psql \
  "host=${YC_PG_HOST} port=${YC_PG_PORT} dbname=${YC_PG_DB} user=${DBT_USER} sslmode=disable connect_timeout=10" \
  -Atc "select current_user;"

systemctl restart sfrfr-api
sleep 2
systemctl is-active sfrfr-api
curl -sS -o /dev/null -w "api_health=%{http_code}\n" http://127.0.0.1:8011/health || true

python3 - <<'PY'
from pathlib import Path
import re
env = Path("/opt/sfrfr/.env").read_text().splitlines()
for k in ("SUPABASE_URL", "DATABASE_URL", "DBT_HOST", "DBT_USER", "DBT_SSLMODE"):
    for line in env:
        if line.startswith(k + "="):
            v = re.sub(r":([^:@/]+)@", ":***@", line.split("=", 1)[1])
            print(f"{k}={v[:90]}")
PY
echo "OK switch db to yc"
