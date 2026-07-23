#!/usr/bin/env bash
# Обёртка: полный сид ТЗ-02 (лендинг + оферта + ПДн + согласие + MAX + форма).
# См. scripts/wp_seed_site_tz02.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/wp_seed_site_tz02.sh" "$@"
