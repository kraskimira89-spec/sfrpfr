#!/usr/bin/env bash
set -euo pipefail
SITE_DIR=/var/www/taxi-doroga-dobra
export SFRFR_HOME_PATH=/opt/sfrfr/scripts/assets/sfrfr-home.html
export SFRFR_CSS_PATH=/opt/sfrfr/scripts/assets/sfrfr-landing.css
export SFRFR_BLOG_ASSETS=/opt/sfrfr/scripts/assets/blog
MAX_CHAT_URL="$(grep -m1 '^MAX_CHAT_URL=' /opt/sfrfr/.env | cut -d= -f2- | tr -d '"\r' || true)"
MAX_PUBLIC_BOT_URL="$(grep -m1 '^MAX_PUBLIC_BOT_URL=' /opt/sfrfr/.env | cut -d= -f2- | tr -d '"\r' || true)"
export MAX_CHAT_URL MAX_PUBLIC_BOT_URL
echo "CHAT=${MAX_CHAT_URL:-} PUB=${MAX_PUBLIC_BOT_URL:-}"
cd /opt/sfrfr && git log -1 --oneline
wp --allow-root --path="$SITE_DIR" eval-file /opt/sfrfr/scripts/wp_apply_landing_css.php
wp --allow-root --path="$SITE_DIR" eval-file /opt/sfrfr/scripts/wp_apply_home.php
echo
wp --allow-root --path="$SITE_DIR" eval-file /opt/sfrfr/scripts/wp_seed_blog_tz11.php
echo DONE
