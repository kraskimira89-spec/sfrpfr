# Деплой: WordPress + API на VPS (reg.ru)

## Топология

```text
домен taxi-doroga-dobra.ru (reg.ru DNS)
├── taxi-doroga-dobra.ru      → WordPress (витрина / посадочная SFRFR)
│                                 папка отдельно от API, напр. /var/www/taxi-doroga-dobra
└── api.taxi-doroga-dobra.ru  → FastAPI SFRFR (uvicorn + nginx)
                              │
                              ├─ код: /opt/sfrfr
                              ├─ HTTPS webhook MAX
                              └─ LLM → Yandex AI Studio
```

Автодеплой: `push` в `main` → GitHub Actions (`deploy-vps.yml`) → SSH → `scripts/vps_deploy.sh` в `/opt/sfrfr`.

## 1. Один раз на VPS (bootstrap)

Подставьте URL репозитория и пользователя SSH:

```bash
# на VPS
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip

# клон временно или скопируйте скрипт
sudo REPO_URL=git@github.com:kraskimira89-spec/sfrpfr.git \
  APP_DIR=/opt/sfrfr \
  APP_USER=sfrfr \
  bash scripts/vps_bootstrap.sh
```

Создаётся:

- каталог `/opt/sfrfr`
- пользователь `sfrfr`
- venv + зависимости
- `.env` из `.env.example` (заполните секреты)
- systemd `sfrfr-api.service` на `127.0.0.1:8011` (порт 8000 на VPS часто занят Docker/другими API)

На VPS должен быть deploy-ключ GitHub (read) у пользователя `sfrfr`, либо HTTPS с токеном.

## 2. Секреты GitHub Actions

Пошагово: [vps-secrets-checklist.md](vps-secrets-checklist.md)

Быстрый скрипт с ПК:

```powershell
.\scripts\setup_github_vps_secrets.ps1 -VpsHost YOUR_IP -VpsUser root
```

В репозитории → Settings → Secrets and variables → Actions:

| Secret | Значение |
|--------|----------|
| `VPS_HOST` | IP или hostname VPS |
| `VPS_USER` | SSH-пользователь с правом `sudo` на restart/deploy |
| `VPS_SSH_KEY` | Приватный SSH-ключ (полный PEM) |
| `VPS_PORT` | Опционально, по умолчанию 22 |

Пользователю нужен sudo без пароля на:

```text
/opt/sfrfr/scripts/vps_deploy.sh
systemctl restart sfrfr-api
```

Пример `/etc/sudoers.d/sfrfr-deploy`:

```text
deploy ALL=(root) NOPASSWD: /bin/bash /opt/sfrfr/scripts/vps_deploy.sh, /bin/systemctl restart sfrfr-api, /bin/systemctl is-active sfrfr-api
```

## 3. Автокоммит и пуш (локально / Cursor)

```powershell
.\scripts\auto_commit_push.ps1
.\scripts\auto_commit_push.ps1 -Message "feat: sync"
```

Cursor hook: после `stop` агента вызывается `.cursor/hooks/auto-commit-push.ps1` (см. `.cursor/hooks.json`).  
Не коммитит `.env` (gitignore + проверка индекса).

## 4. DNS (reg.ru)

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | IP VPS |
| A | `api` | IP VPS |
| A | `www` | IP VPS (опционально) |

SSL: Let's Encrypt (certbot). Для MAX webhook нужен **валидный HTTPS**.

## 5. Nginx (эскиз)

```nginx
# api.taxi-doroga-dobra.ru
server {
    listen 443 ssl http2;
    server_name api.taxi-doroga-dobra.ru;

    location / {
        proxy_pass http://127.0.0.1:8011;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# taxi-doroga-dobra.ru — витрина WordPress (отдельная папка)
server {
    listen 443 ssl http2;
    server_name taxi-doroga-dobra.ru www.taxi-doroga-dobra.ru;

    root /var/www/taxi-doroga-dobra;
    index index.php index.html;

    location / {
        try_files $uri $uri/ /index.php?$args;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php-fpm.sock;
    }
}
```

## Env на VPS

Файл `/opt/sfrfr/.env` (заполнить ключи; сервис уже слушает `127.0.0.1:8011`):

```env
PUBLIC_BASE_URL=https://api.taxi-doroga-dobra.ru
AI_PROVIDER=yandex
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
MAX_BOT_TOKEN=...
MAX_WEBHOOK_SECRET=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
DATABASE_URL=...
```

Проверка на сервере:

```bash
curl -s http://127.0.0.1:8011/health
systemctl status sfrfr-api
```

Миграции Supabase (облако после `supabase link`):

```powershell
npx supabase db push
```

## 7. Связка с WordPress

- Кнопка «Написать в MAX» на лендинге.
- ПДн-сканы не через WP-формы; загрузка — MAX / кабинет API.
- `service_role` только на сервере API, не в JS.
