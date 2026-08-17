#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DBT_DIR="$ROOT/analytics"
ENV_FILE="${SFRFR_ENV_FILE:-$ROOT/.env}"

load_dotenv() {
  local file="$1" line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "${line//[[:space:]]/}" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    # trim surrounding quotes
    if [[ "$val" == \"*\" && "$val" == *\" ]]; then
      val="${val:1:${#val}-2}"
    elif [[ "$val" == \'*\' && "$val" == *\' ]]; then
      val="${val:1:${#val}-2}"
    fi
    export "$key=$val"
  done <"$file"
}

# Не `source` .env: пути с пробелами (Google Calendar json) ломают bash.
# systemd EnvironmentFile тоже ок; load_dotenv дополняет ручной запуск.
if [[ -f "$ENV_FILE" ]]; then
  load_dotenv "$ENV_FILE"
fi

: "${DBT_HOST:?DBT_HOST must be set}"
: "${DBT_PASSWORD:?DBT_PASSWORD must be set}"
# Канон YC: прямой Postgres :5433 (не Supavisor :5432).
export DBT_PORT="${DBT_PORT:-5433}"
export DBT_SSLMODE="${DBT_SSLMODE:-disable}"
if [[ "$DBT_PORT" == "5432" ]]; then
  echo "WARN: DBT_PORT=5432 (часто Supavisor). Для YC dbt канон — 5433." >&2
fi

if [[ ! -f "$DBT_DIR/profiles.yml" ]]; then
  echo "Missing $DBT_DIR/profiles.yml. Copy profiles.yml.example and keep DBT_PASSWORD in .env." >&2
  exit 1
fi

export DBT_SEND_ANONYMOUS_USAGE_STATS="${DBT_SEND_ANONYMOUS_USAGE_STATS:-false}"
cd "$DBT_DIR"
DBT_BIN="${DBT_BIN:-$ROOT/.venv/bin/dbt}"
if [[ ! -x "$DBT_BIN" ]]; then
  DBT_BIN="$(command -v dbt)"
fi

"$DBT_BIN" debug --profiles-dir .
# Direct Postgres (YC :5433 или Cloud direct); последовательно.
"$DBT_BIN" build --profiles-dir . --threads 1 --no-populate-cache
"$ROOT/scripts/dbt_apply_rls.sh"
"$DBT_BIN" docs generate --profiles-dir . --threads 1 --no-populate-cache || true
