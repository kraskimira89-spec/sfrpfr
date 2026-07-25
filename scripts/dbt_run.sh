#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DBT_DIR="$ROOT/analytics"
ENV_FILE="${SFRFR_ENV_FILE:-$ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${DBT_HOST:?DBT_HOST must be set}"
: "${DBT_PASSWORD:?DBT_PASSWORD must be set}"

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
# Нужен direct PostgreSQL endpoint с IPv4 add-on; pooler для DDL dbt ненадёжен.
"$DBT_BIN" build --profiles-dir .
"$DBT_BIN" docs generate --profiles-dir .
