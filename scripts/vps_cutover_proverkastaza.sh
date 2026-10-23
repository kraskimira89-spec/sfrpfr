#!/usr/bin/env bash
# Cutover витрины/API/кабинетов на proverkastaza.ru.
# Требования: DNS A-записи уже на 91.229.11.147 (см. docs/ops/dns-proverkastaza.md).
#
#   sudo bash /opt/sfrfr/scripts/vps_cutover_proverkastaza.sh
#   sudo SKIP_DNS_CHECK=1 bash ...   # если dig ещё кэширует, но A уже верный
#
# Для 301 с бывшего apex (если ещё жив в DNS):
#   sudo OLD_ROOT=<бывший-apex.ru> bash /opt/sfrfr/scripts/vps_cutover_proverkastaza.sh
# OLD_ROOT в репозитории не храним — только аргумент окружения.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
SITE_DIR="${SITE_DIR:-/var/www/proverkastaza}"
VPS_IP="${VPS_IP:-91.229.11.147}"
NEW_ROOT="proverkastaza.ru"
OLD_ROOT="${OLD_ROOT:-}"
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

if [[ -n "$OLD_ROOT" ]]; then
  echo "==> HTTP 301 с бывшего apex $OLD_ROOT → $NEW_ROOT"
  cat >/etc/apache2/sites-available/"$OLD_ROOT".conf <<EOF
<VirtualHost *:80>
    ServerName ${OLD_ROOT}
    ServerAlias www.${OLD_ROOT}
    RewriteEngine On
    RewriteRule ^ https://${NEW_ROOT}%{REQUEST_URI} [R=301,L]
</VirtualHost>
EOF
  a2ensite "$OLD_ROOT".conf >/dev/null
else
  echo "==> OLD_ROOT не задан — HTTP 301 с бывшего apex пропускаем"
fi

apachectl configtest
systemctl reload apache2

ensure_ssl_redirect() {
  local conf="$1"
  local target="$2"
  [[ -f "$conf" ]] || return 0
  if grep -q "RewriteRule \^ https://${target}" "$conf"; then
    return 0
  fi
  # Упрощённый патч: вставить Rewrite перед закрытием VirtualHost
  if ! grep -q "RewriteEngine" "$conf"; then
    sed -i "/<\/VirtualHost>/i\\    RewriteEngine On\\n    RewriteRule ^ https://${target}%{REQUEST_URI} [R=301,L]" "$conf"
  fi
}

run_certbot() {
  certbot --apache --non-interactive --agree-tos -m "$EMAIL_LE" "$@" || true
}

echo "==> Let's Encrypt (если ещё нет)"
run_certbot -d "$NEW_ROOT" -d "www.$NEW_ROOT"
run_certbot -d "api.$NEW_ROOT"
run_certbot -d "cabinet.$NEW_ROOT"
run_certbot -d "admin.$NEW_ROOT"
run_certbot -d "proverka-staza.ru" -d "www.proverka-staza.ru"
run_certbot -d "prostaz.ru" -d "www.prostaz.ru"

# Certbot --apache ломает алиасы: комментирует кросс-доменный 301, плодит *:80 в *-le-ssl.
# Ставим чистые HTTP+HTTPS редиректы из репо и глушим отдельные certbot-vhosts алиасов.
install -m 644 "$APP_DIR/docs/apache-vhost-redirect-aliases.conf" \
  /etc/apache2/sites-available/redirect-proverkastaza-aliases.conf
install -m 644 "$APP_DIR/docs/apache-vhost-redirect-aliases-le-ssl.conf" \
  /etc/apache2/sites-available/redirect-proverkastaza-aliases-le-ssl.conf
for f in proverka-staza.ru-le-ssl.conf prostaz.ru-le-ssl.conf \
         www.proverka-staza.ru-le-ssl.conf www.prostaz.ru-le-ssl.conf; do
  a2dissite "$f" 2>/dev/null || true
done
a2ensite redirect-proverkastaza-aliases.conf >/dev/null
a2ensite redirect-proverkastaza-aliases-le-ssl.conf >/dev/null

if [[ -n "$OLD_ROOT" ]]; then
  echo "==> SSL 301 с бывшего apex/поддоменов"
  if [[ -f /etc/apache2/sites-available/"$OLD_ROOT"-le-ssl.conf ]]; then
    ensure_ssl_redirect /etc/apache2/sites-available/"$OLD_ROOT"-le-ssl.conf "$NEW_ROOT"
  fi
  ensure_ssl_redirect /etc/apache2/sites-available/"api.$OLD_ROOT"-le-ssl.conf "api.$NEW_ROOT"
  ensure_ssl_redirect /etc/apache2/sites-available/"cabinet.$OLD_ROOT"-le-ssl.conf "cabinet.$NEW_ROOT"
  ensure_ssl_redirect /etc/apache2/sites-available/"admin.$OLD_ROOT"-le-ssl.conf "admin.$NEW_ROOT"

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
fi

apachectl configtest
systemctl reload apache2

echo "==> WordPress URL → https://$NEW_ROOT"
if command -v wp >/dev/null && [[ -d "$SITE_DIR" ]]; then
  wp --path="$SITE_DIR" --allow-root option update home "https://$NEW_ROOT"
  wp --path="$SITE_DIR" --allow-root option update siteurl "https://$NEW_ROOT"
  if [[ -n "$OLD_ROOT" ]]; then
    wp --path="$SITE_DIR" --allow-root search-replace \
      "https://$OLD_ROOT" "https://$NEW_ROOT" \
      --all-tables --skip-columns=guid --report-changed-only || true
    wp --path="$SITE_DIR" --allow-root search-replace \
      "http://$OLD_ROOT" "https://$NEW_ROOT" \
      --all-tables --skip-columns=guid --report-changed-only || true
    wp --path="$SITE_DIR" --allow-root search-replace \
      "https://cabinet.$OLD_ROOT" "https://cabinet.$NEW_ROOT" \
      --all-tables --skip-columns=guid --report-changed-only || true
  fi
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
replace_env "$ENVF" "CABINET_PUBLIC_URL" "https://cabinet.$NEW_ROOT"
replace_env "$ENVF" "ADMIN_PUBLIC_URL" "https://admin.$NEW_ROOT"
replace_env "$ENVF" "MAX_MINIAPP_URL" "https://$NEW_ROOT/app/"
replace_env "$ENVF" "SITE_URL" "https://$NEW_ROOT"
replace_env "$ENVF" "YOOKASSA_RETURN_URL" "https://$NEW_ROOT/"

for app_env in "$APP_DIR/apps/cabinet/.env" "$APP_DIR/apps/admin/.env"; do
  replace_env "$app_env" "NEXT_PUBLIC_API_BASE_URL" "https://api.$NEW_ROOT"
  replace_env "$app_env" "NEXT_PUBLIC_CABINET_PUBLIC_URL" "https://cabinet.$NEW_ROOT"
done

echo "==> Cutover done → https://$NEW_ROOT"
if [[ -n "$OLD_ROOT" ]]; then
  echo "    Legacy 301: $OLD_ROOT → $NEW_ROOT"
fi
