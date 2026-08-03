#!/usr/bin/env bash
# Включить Auth Send Email Hook на staging self-host → API SFRFR → Яндекс SMTP.
# Требует GOTRUE_HOOK_SEND_EMAIL_SECRETS в .env (тот же формат v1,whsec_… что SUPABASE_SEND_EMAIL_HOOK_SECRET).
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/sfrfr-supabase/supabase/docker}"
HOOK_URI="${GOTRUE_HOOK_SEND_EMAIL_URI:-https://api.proverkastaza.ru/api/integrations/supabase/auth-send-email}"
OVERLAY_SRC="${OVERLAY_SRC:-/tmp/docker-compose.sfrfr-email.yml}"

cd "$COMPOSE_DIR"

if [[ ! -f "$OVERLAY_SRC" ]]; then
  echo "FAIL: missing overlay $OVERLAY_SRC" >&2
  exit 1
fi
cp -f "$OVERLAY_SRC" ./docker-compose.sfrfr-email.yml

SECRET="${GOTRUE_HOOK_SEND_EMAIL_SECRETS:-}"
if [[ -z "$SECRET" ]]; then
  echo "FAIL: set GOTRUE_HOOK_SEND_EMAIL_SECRETS (v1,whsec_…)" >&2
  exit 1
fi

python3 - <<PY
from pathlib import Path
p = Path(".env")
repl = {
    "GOTRUE_HOOK_SEND_EMAIL_ENABLED": "true",
    "GOTRUE_HOOK_SEND_EMAIL_URI": """${HOOK_URI}""",
    "GOTRUE_HOOK_SEND_EMAIL_SECRETS": """${SECRET}""",
    "SMTP_ADMIN_EMAIL": "proverkastaza@yandex.ru",
    "SMTP_SENDER_NAME": "Проверка стажа. Личный кабинет",
    # не трогаем фейковый inbucket, пока хук включён — GoTrue уйдёт в hook
}
text = p.read_text(encoding="utf-8")
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
print("env_hook_ok")
PY

# Caddy + email overlays (если caddy уже в работе)
files=(-f docker-compose.yml)
[[ -f docker-compose.caddy.yml ]] && files+=(-f docker-compose.caddy.yml)
files+=(-f docker-compose.sfrfr-email.yml)

docker compose "${files[@]}" up -d auth
sleep 5
docker compose "${files[@]}" ps auth
docker compose "${files[@]}" exec -T auth wget -qO- http://127.0.0.1:9999/health || true
echo "OK: Send Email Hook → ${HOOK_URI}"
