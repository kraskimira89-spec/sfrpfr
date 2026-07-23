# Деплой: WordPress + API на VPS (reg.ru)

## Топология

```text
домен taxi-doroga-dobra.ru (reg.ru DNS)
├── taxi-doroga-dobra.ru      → WordPress (витрина / посадочная SFRFR)
│                                 папка: /var/www/taxi-doroga-dobra
│   └── /app/                → мини-приложение MAX (статика web/max-miniapp)
└── api.taxi-doroga-dobra.ru  → FastAPI SFRFR (uvicorn + Apache proxy)
                              │
                              ├─ код: /opt/sfrfr
                              ├─ HTTPS webhook MAX
                              └─ LLM → Yandex AI Studio
```

Витрина: `/var/www/taxi-doroga-dobra` (Apache). На VPS уже Apache/PHP/MySQL — nginx не используем.

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

Домен: `taxi-doroga-dobra.ru`. IP VPS: **`91.229.11.147`**.

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `91.229.11.147` |
| A | `api` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |

SSL: Let's Encrypt (certbot). Для MAX webhook нужен **валидный HTTPS**.

## 5. Apache (на нашем VPS — не nginx)

Порты 80/443 заняты Apache. Конфиги в репозитории:

- `docs/apache-vhost-taxi-doroga-dobra.ru.conf` → `/var/www/taxi-doroga-dobra`
- `docs/apache-vhost-api.taxi-doroga-dobra.ru.conf` → proxy на `127.0.0.1:8011`

После `a2ensite` + `certbot --apache` появляются `*-le-ssl.conf` (HTTPS + redirect).

```apache
# api.taxi-doroga-dobra.ru (эскиз HTTP; SSL добавляет certbot)
<VirtualHost *:80>
    ServerName api.taxi-doroga-dobra.ru
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8011/
    ProxyPassReverse / http://127.0.0.1:8011/
</VirtualHost>
```

```apache
# taxi-doroga-dobra.ru — витрина (DocumentRoot)
<VirtualHost *:80>
    ServerName taxi-doroga-dobra.ru
    ServerAlias www.taxi-doroga-dobra.ru
    DocumentRoot /var/www/taxi-doroga-dobra
    <Directory /var/www/taxi-doroga-dobra>
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>
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

- Витрина: https://taxi-doroga-dobra.ru/ → `/var/www/taxi-doroga-dobra` (WP ru_RU, тема **Astra** + **Spectra**).
- Админ: https://taxi-doroga-dobra.ru/wp-admin/ — логин/пароль в `/root/.sfrfr-secrets/wp-taxi-doroga-dobra.env` на VPS.
- Стек (в репо GitHub): `scripts/wp_install_stack.sh`
  - Astra + Spectra (без Elementor);
  - WPForms Lite (заявки; **не** сканы ПДн);
  - Rank Math SEO, UpdraftPlus, Wordfence, **WP Super Cache** (Apache);
  - не ставим: LiteSpeed Cache, Really Simple SSL (SSL уже certbot).
- Сид ТЗ-02: `scripts/wp_seed_site_tz02.sh` (обёртка `scripts/wp_seed_landing.sh`) — главная, оферта, политика ПДн, согласие, меню, CTA MAX, WPForms-лид.
- Дизайн главной: `scripts/assets/sfrfr-home.html` + `scripts/assets/sfrfr-landing.css` (синий `#1E4E79`, акцент `#2E7D5B`, Manrope).
- Форма лида: `scripts/wp_ensure_lead_form.php` (имя, телефон/канал, согласие; без файлов и СНИЛС; entries + email admin).
- Страницы: `/`, `/oferta/`, `/politika-pdn/`, `/soglasie/` (HTTPS).
- Мини-приложение MAX (кабинет v1): `https://taxi-doroga-dobra.ru/app/` — исходники `web/max-miniapp/`, выкладка `scripts/deploy_max_miniapp.sh`.
- В кабинете MAX: **Чат-боты → «Стаж и пенсия» → Расширенные настройки** → URL `https://taxi-doroga-dobra.ru/app/` → Сохранить.
- Диплинк: `https://max.ru/id8905998693_1_bot?startapp` (`MAX_PUBLIC_BOT_URL`) — подставить в кнопку на лендинге WP. Используйте технический username из `/me`, а не отображаемое имя бота.
- API для кабинета: `POST /api/cases/open`, `GET /api/cases/{id}`, `POST /api/documents/upload`, `POST /api/cases/{id}/run` (+ CORS с витрины).
- Для корректной работы MAX API нужны сертификаты Минцифры в `certs/` (см. `sfrfr.integrations.max.ssl_context`).
- Webhook API: `https://api.taxi-doroga-dobra.ru/api/integrations/max/webhook` (`PUBLIC_BASE_URL` на VPS). Подписка: `sfrfr max-subscribe` после заполнения `MAX_BOT_TOKEN`.
- ПДн-сканы не через WP-формы; загрузка — MAX / кабинет `/app/`.
- `service_role` только на сервере API, не в JS.
