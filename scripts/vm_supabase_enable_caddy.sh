#!/usr/bin/env bash
# Включить Caddy (TLS) перед Kong на staging Supabase ВМ.
# Требует DNS: supabase.proverkastaza.ru A → публичный IP ВМ (иначе LE не выдаст сертификат).
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
DOMAIN="${PROXY_DOMAIN:-supabase.proverkastaza.ru}"
EMAIL="${CERTBOT_EMAIL:-ops@proverkastaza.ru}"

cd "$COMPOSE_DIR"

python3 - <<PY
from pathlib import Path
p = Path(".env")
text = p.read_text(encoding="utf-8")
repl = {
    "PROXY_DOMAIN": "${DOMAIN}",
    "CERTBOT_EMAIL": "${EMAIL}",
    "API_EXTERNAL_URL": "https://${DOMAIN}",
    "SUPABASE_PUBLIC_URL": "https://${DOMAIN}",
}
lines = []
seen = set()
for ln in text.splitlines():
    if "=" in ln and not ln.strip().startswith("#"):
        k = ln.split("=", 1)[0]
        if k in repl:
            lines.append(f"{k}={repl[k]}")
            seen.add(k)
            continue
    lines.append(ln)
for k, v in repl.items():
    if k not in seen:
        lines.append(f"{k}={v}")
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("env_ok", "${DOMAIN}")
PY

docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d
sleep 8
docker compose -f docker-compose.yml -f docker-compose.caddy.yml ps
echo "HINT: если caddy unhealthy — проверьте DNS A ${DOMAIN} → IP этой ВМ"
