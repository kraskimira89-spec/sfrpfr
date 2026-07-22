#!/usr/bin/env bash
# Выкладка мини-приложения MAX на витрину:
#   https://taxi-doroga-dobra.ru/app/
# Использование на VPS (из /opt/sfrfr после git pull):
#   bash scripts/deploy_max_miniapp.sh
# Или с ПК через SSH, указав SRC.

set -euo pipefail

SRC="${SRC:-}"
if [[ -z "$SRC" ]]; then
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  SRC="$ROOT/web/max-miniapp"
fi
DEST="${DEST:-/var/www/taxi-doroga-dobra/app}"

if [[ ! -f "$SRC/index.html" ]]; then
  echo "нет $SRC/index.html" >&2
  exit 1
fi

mkdir -p "$DEST"
rsync -a --delete \
  --exclude '.git' \
  "$SRC/" "$DEST/"

chown -R www-data:www-data "$DEST" 2>/dev/null || true
find "$DEST" -type d -exec chmod 755 {} \;
find "$DEST" -type f -exec chmod 644 {} \;

echo "deployed -> $DEST"
ls -la "$DEST"
