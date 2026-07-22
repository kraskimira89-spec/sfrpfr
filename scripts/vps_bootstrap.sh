#!/usr/bin/env bash
# Первичная настройка каталога проекта на VPS.
# Запуск на сервере от root или пользователя с sudo:
#   curl -sL ... | bash   ИЛИ   bash scripts/vps_bootstrap.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
APP_USER="${APP_USER:-sfrfr}"
REPO_URL="${REPO_URL:-git@github.com:kraskimira89-spec/sfrpfr.git}"
BRANCH="${BRANCH:-main}"

echo "==> Пользователь $APP_USER"
if ! id "$APP_USER" &>/dev/null; then
  useradd --system --create-home --shell /bin/bash "$APP_USER"
fi

echo "==> Каталог $APP_DIR"
mkdir -p "$APP_DIR"
mkdir -p /var/log/sfrfr

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR" /var/log/sfrfr

echo "==> Python venv"
sudo -u "$APP_USER" bash -lc "
  cd '$APP_DIR'
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install -e '.[ai]'
"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "Создан $APP_DIR/.env — заполните секреты!"
fi

echo "==> systemd unit"
cat >/etc/systemd/system/sfrfr-api.service <<EOF
[Unit]
Description=SFRFR FastAPI
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn sfrfr.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/var/log/sfrfr/api.log
StandardError=append:/var/log/sfrfr/api.err

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sfrfr-api
systemctl restart sfrfr-api || true

echo "==> Готово. Проверьте: systemctl status sfrfr-api"
echo "    Каталог проекта: $APP_DIR"
