#!/usr/bin/env bash
# Обновить отдельные ключи в /opt/sfrfr/.env без печати значений.
set -euo pipefail
ENV_FILE=/opt/sfrfr/.env
KEY="$1"
VALUE="$2"
python3 - "$ENV_FILE" "$KEY" "$VALUE" <<'PY'
from pathlib import Path
import sys
path, key, value = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
out, seen = [], False
for line in lines:
    if line.startswith(f"{key}="):
        out.append(f"{key}={value}")
        seen = True
    else:
        out.append(line)
if not seen:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"updated {key} len={len(value)}")
PY
chown sfrfr:sfrfr "$ENV_FILE"
chmod 600 "$ENV_FILE"
