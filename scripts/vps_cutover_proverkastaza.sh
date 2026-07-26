#!/usr/bin/env bash
# Cutover витрины/API/кабинетов на proverkastaza.ru.
# Требования: DNS A-записи уже на 91.229.11.147 (см. docs/ops/dns-proverkastaza.md).
#
#   sudo bash /opt/sfrfr/scripts/vps_cutover_proverkastaza.sh
#   sudo SKIP_DNS_CHECK=1 bash ...   # если dig ещё кэширует, но A уже верный
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
VPS_IP="${VPS_IP:-91.229.11.147}"
NEW_ROOT="proverkastaza.ru"
OLD_ROOT="taxi-doroga-dobra.ru"
EMAIL_LE="${EMAIL_LE:-admin@proverkastaza.ru}"

need_hosts=(
  "$NEW_ROOT"
  "www.$NEW_ROOT"
  "api.$NEW_ROOT"
  "cabinet.$NEW_ROOT"
  "admin.$NEW_ROOT"
  "proverka-staza.ru"
  "www.proverka-staza.ru"
  "prostaz.ru"
  "www.prostaz.ru"
)

resolve_ok() {
  local host="$1"
  local got
  got="$(dig +short "$host" A | head -n1 || true)"
  [[ "$got" == "$VPS_IP" ]]
}

echo "==> Проверка DNS → $VPS_IP"
dns_fail=0
for h in "${need_hosts[@]}"; do
  if resolve_ok "$h"; then
    echo "  OK  $h"
  else
    echo "  FAIL $h (ожидали $VPS_IP)"
    dns_fail=1
  fi
done
if [[ "$dns_fail" -ne 0 && "${SKIP_DNS_CHECK:-0}" != "1" ]]; then
  echo "Сначала выставьте A-записи в reg.ru (docs/ops/dns-proverkastaza.md)."
  echo "Или: SKIP_DNS_CHECK=1 (certbot может упасть)."
  exit 1
fi

echo "==> Apache vhosts из $APP_DIR/docs"
install -m 644 "$APP_DIR/docs/apache-vhost-proverkastaza.ru.conf" \
  /etc/apache2/sites-available/proverkastaza.ru.conf
install -m 644 "$APP_DIR/docs/apache-vhost-api.proverkastaza.ru.conf" \
  /etc/apache2/sites-available/api.proverkastaza.ru.conf
install -m 644 "$APP_DIR/docs/apache-vhost-cabinet.proverkastaza.ru.conf" \
  /etc/apache2/sites-available/cabinet.proverkastaza.ru.conf
install -m 644 "$APP_DIR/docs/apache-vhost-admin.proverkastaza.ru.conf" \
  /etc/apache2/sites-available/admin.proverkastaza.ru.conf
install -m 644 "$APP_DIR/docs/apache-vhost-redirect-aliases.conf" \
  /etc/apache2/sites-available/redirect-proverkastaza-aliases.conf

a2enmod rewrite headers proxy proxy_http ssl >/dev/null
a2ensite proverkastaza.ru.conf \
  api.proverkastaza.ru.conf \
  cabinet.proverkastaza.ru.conf \
  admin.proverkastaza.ru.conf \
  redirect-proverkastaza-aliases.conf >/dev/null

# Старый DocumentRoot-vhost → HTTP 301 (SSL-vhost патчим ниже)
cat >/etc/apache2/sites-available/taxi-doroga-dobra.ru.conf <<EOF
<VirtualHost *:80>
    ServerName taxi-doroga-dobra.ru
    ServerAlias www.taxi-doroga-dobra.ru
    RewriteEngine On
    RewriteRule ^ https://${NEW_ROOT}%{REQUEST_URI} [R=301,L]
</VirtualHost>
EOF
a2ensite taxi-doroga-dobra.ru.conf >/dev/null
# Старые api/cabinet/admin оставляем до редирект-патча SSL (ниже)

apachectl configtest
systemctl reload apache2

ensure_ssl_redirect() {
  local conf="$1"
  local target="$2"
  [[ -f "$conf" ]] || return 0
  if grep -q "RewriteRule \^ https://${target}" "$conf"; then
    return 0
  fi
  # Вставка перед </VirtualHost> последнего блока
  python3 - "$conf" "$target" <<'PY'
import sys
path, target = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
snippet = (
    "\n    RewriteEngine On\n"
    f"    RewriteRule ^ https://{target}%{{REQUEST_URI}} [R=301,L]\n"
)
if f"https://{target}" in text and "RewriteRule" in text:
    sys.exit(0)
idx = text.rfind("</VirtualHost>")
if idx < 0:
    sys.exit(0)
text = text[:idx] + snippet + text[idx:]
open(path, "w", encoding="utf-8").write(text)
print(f"  patched redirect in {path} → {target}")
PY
}

echo "==> Let's Encrypt (certbot)"
run_certbot() {
  certbot --apache --non-interactive --agree-tos -m "$EMAIL_LE" --redirect "$@" \
    || echo "WARN: certbot failed for: $*"
}
run_certbot -d "$NEW_ROOT" -d "www.$NEW_ROOT"
run_certbot -d "api.$NEW_ROOT"
run_certbot -d "cabinet.$NEW_ROOT"
run_certbot -d "admin.$NEW_ROOT"
run_certbot -d "proverka-staza.ru" -d "www.proverka-staza.ru"
run_certbot -d "prostaz.ru" -d "www.prostaz.ru"

# HTTPS-редиректы с алиасов (certbot создаёт *-le-ssl.conf без кросс-доменного 301)
ensure_ssl_redirect /etc/apache2/sites-available/proverka-staza.ru-le-ssl.conf "$NEW_ROOT"
ensure_ssl_redirect /etc/apache2/sites-available/prostaz.ru-le-ssl.conf "$NEW_ROOT"
# Имена файлов certbot могут совпадать с ServerName из redirect-конфига
for f in /etc/apache2/sites-available/*proverka-staza*-le-ssl.conf \
         /etc/apache2/sites-available/*prostaz*-le-ssl.conf; do
  [[ -e "$f" ]] || continue
  ensure_ssl_redirect "$f" "$NEW_ROOT"
done

# Старый корневой домен: SSL-vhost → 301 на новый (сохраняем сертификат)
if [[ -f /etc/apache2/sites-available/taxi-doroga-dobra.ru-le-ssl.conf ]]; then
  ensure_ssl_redirect /etc/apache2/sites-available/taxi-doroga-dobra.ru-le-ssl.conf "$NEW_ROOT"
fi

# Старые поддомены → новые
ensure_ssl_redirect /etc/apache2/sites-available/api.taxi-doroga-dobra.ru-le-ssl.conf "api.$NEW_ROOT"
ensure_ssl_redirect /etc/apache2/sites-available/cabinet.taxi-doroga-dobra.ru-le-ssl.conf "cabinet.$NEW_ROOT"
ensure_ssl_redirect /etc/apache2/sites-available/admin.taxi-doroga-dobra.ru-le-ssl.conf "admin.$NEW_ROOT"

# HTTP старых api/cabinet/admin — тоже 301
for pair in \
  "api.$OLD_ROOT|api.$NEW_ROOT" \
  "cabinet.$OLD_ROOT|cabinet.$NEW_ROOT" \
  "admin.$OLD_ROOT|admin.$NEW_ROOT"; do
  old="${pair%%|*}"
  new="${pair##*|}"
  conf="/etc/apache2/sites-available/${old}.conf"
  [[ -f "$conf" ]] || continue
  cat >"$conf" <<EOF
<VirtualHost *:80>
    ServerName ${old}
    RewriteEngine On
    RewriteRule ^ https://${new}%{REQUEST_URI} [R=301,L]
</VirtualHost>
EOF
done

apachectl configtest
systemctl reload apache2

echo "==> WordPress URL → https://$NEW_ROOT"
if command -v wp >/dev/null && [[ -d "$SITE_DIR" ]]; then
  wp --path="$SITE_DIR" --allow-root option update home "https://$NEW_ROOT"
  wp --path="$SITE_DIR" --allow-root option update siteurl "https://$NEW_ROOT"
  wp --path="$SITE_DIR" --allow-root search-replace \
    "https://$OLD_ROOT" "https://$NEW_ROOT" \
    --all-tables --skip-columns=guid --report-changed-only || true
  wp --path="$SITE_DIR" --allow-root search-replace \
    "http://$OLD_ROOT" "https://$NEW_ROOT" \
    --all-tables --skip-columns=guid --report-changed-only || true
  wp --path="$SITE_DIR" --allow-root search-replace \
    "https://cabinet.$OLD_ROOT" "https://cabinet.$NEW_ROOT" \
    --all-tables --skip-columns=guid --report-changed-only || true
  wp --path="$SITE_DIR" --allow-root cache flush || true
else
  echo "WARN: wp-cli или $SITE_DIR недоступны — обновите home/siteurl вручную"
fi

echo "==> /opt/sfrfr/.env и apps/*/.env"
replace_env() {
  local file="$1"
  local key="$2"
  local val="$3"
  [[ -f "$file" ]] || return 0
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$file"
  else
    echo "${key}=${val}" >>"$file"
  fi
}

ENVF="$APP_DIR/.env"
replace_env "$ENVF" "PUBLIC_BASE_URL" "https://api.$NEW_ROOT"
replace_env "$ENVF" "MAX_MINIAPP_URL" "https://$NEW_ROOT/app/"
replace_env "$ENVF" "CABINET_PUBLIC_URL" "https://cabinet.$NEW_ROOT"
replace_env "$ENVF" "ADMIN_PUBLIC_URL" "https://admin.$NEW_ROOT"
replace_env "$ENVF" "CORS_ALLOWED_ORIGINS" \
  "https://$NEW_ROOT,https://www.$NEW_ROOT,https://cabinet.$NEW_ROOT,https://admin.$NEW_ROOT,https://$OLD_ROOT,https://cabinet.$OLD_ROOT,https://admin.$OLD_ROOT"

replace_env "$APP_DIR/apps/cabinet/.env" "NEXT_PUBLIC_API_BASE_URL" "https://api.$NEW_ROOT"
replace_env "$APP_DIR/apps/cabinet/.env" "NEXT_PUBLIC_CABINET_PUBLIC_URL" "https://cabinet.$NEW_ROOT"
replace_env "$APP_DIR/apps/admin/.env" "NEXT_PUBLIC_API_BASE_URL" "https://api.$NEW_ROOT"

echo "==> Restart API + rebuild Next.js"
systemctl restart sfrfr-api
bash "$APP_DIR/scripts/vps_deploy.sh" --post-update || {
  systemctl restart sfrfr-cabinet sfrfr-admin 2>/dev/null || true
}

# Мини-приложение уже в SITE_DIR/app — обновится после git pull + deploy_max_miniapp
if [[ -x "$APP_DIR/scripts/deploy_max_miniapp.sh" ]]; then
  bash "$APP_DIR/scripts/deploy_max_miniapp.sh" || true
fi

echo "==> Smoke"
for u in \
  "https://$NEW_ROOT/" \
  "https://api.$NEW_ROOT/health" \
  "https://cabinet.$NEW_ROOT/" \
  "https://admin.$NEW_ROOT/" \
  "https://proverka-staza.ru/" \
  "https://prostaz.ru/" \
  "https://$OLD_ROOT/"; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -L --max-redirs 5 "$u" || echo ERR)"
  echo "  $code  $u"
done

echo
echo "Готово. Дальше вручную:"
echo "  1) MAX mini-app URL → https://$NEW_ROOT/app/"
echo "  2) Supabase Auth redirects → docs/ops/supabase-auth-redirects.md"
echo "  3) sfrfr max-subscribe  (webhook на api.$NEW_ROOT)"
