#!/usr/bin/env bash
# Обёртка: делегирует сид ТЗ 02 (лендинг + оферта + MAX + форма).
# Сохранена для совместимости со старыми вызовами.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/wp_seed_site_tz02.sh" "$@"
