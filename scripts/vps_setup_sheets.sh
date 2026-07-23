#!/usr/bin/env bash
set -euo pipefail
APP=/opt/sfrfr
chown -R sfrfr:sfrfr "$APP/secrets"
chmod 600 "$APP/secrets/sfrfr-sheets-f3f6cf313dc9.json"

python3 <<'PY'
from pathlib import Path

p = Path("/opt/sfrfr/.env")
text = p.read_text(encoding="utf-8")
updates = {
    "GOOGLE_SHEETS_SPREADSHEET_ID": "15Dl7CJnaSZYR9m5o2DaOgcerNJ7mehzyY-KaGbWugIk",
    "GOOGLE_SHEETS_WORKSHEET": "Analytics",
    "GOOGLE_SHEETS_CREDENTIALS_JSON": "secrets/sfrfr-sheets-f3f6cf313dc9.json",
}
lines = text.splitlines()
out = []
seen = set()
for line in lines:
    if not line or line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    k = line.split("=", 1)[0].strip()
    if k in updates:
        out.append(f"{k}={updates[k]}")
        seen.add(k)
    else:
        out.append(line)
missing = [k for k in updates if k not in seen]
if missing:
    if out and out[-1] != "":
        out.append("")
    out.append("# Google Sheets")
    for k in missing:
        out.append(f"{k}={updates[k]}")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("env updated", sorted(updates))
PY

chown sfrfr:sfrfr "$APP/.env"
chmod 600 "$APP/.env"
chown sfrfr:sfrfr "$APP/src/sfrfr/integrations/sheets/__init__.py" "$APP/src/sfrfr/core/config.py"

sudo -u sfrfr bash -lc 'cd /opt/sfrfr && . .venv/bin/activate && pip install -q "google-auth>=2.35.0" && PYTHONPATH=src python -m sfrfr sheets-sync'
