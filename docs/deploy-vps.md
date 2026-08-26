# Деплой: WordPress + API на VPS (reg.ru)

SSH с ПК владельца: `ssh sfrfr-vps` — см. [ops/vps-ssh.md](ops/vps-ssh.md).

## Домены (актуально)

Основной: **proverkastaza.ru**. Алиасы с 301: `proverka-staza.ru`, `prostaz.ru`, старый `taxi-doroga-dobra.ru`.  
DNS: [ops/dns-proverkastaza.md](ops/dns-proverkastaza.md). Cutover на VPS: `scripts/vps_cutover_proverkastaza.sh`.  
Папка WP на диске: `/var/www/taxi-doroga-dobra` (имя каталога не меняли).

## Топология

```text
домен proverkastaza.ru (reg.ru DNS)
├── proverkastaza.ru      → WordPress (витрина / посадочная SFRFR)
│                             папка: /var/www/taxi-doroga-dobra
│   └── /app/            → мини-приложение MAX (статика web/max-miniapp)
├── api.proverkastaza.ru  → FastAPI SFRFR (uvicorn + Apache proxy)
├── cabinet.proverkastaza.ru → Next.js клиент (:3001)
└── admin.proverkastaza.ru   → Next.js staff (:3002)
```

Витрина: `/var/www/taxi-doroga-dobra` (Apache). На VPS уже Apache/PHP/MySQL — nginx не используем.

Автодеплой: `push` в `main` → GitHub Actions (`deploy-vps.yml`) → SSH → `scripts/vps_deploy.sh` в `/opt/sfrfr`.

Очередь: в `deploy-vps.yml` задано `concurrency.group: deploy-vps` и **`cancel-in-progress: false`** — параллельные push не отменяют друг друга, а ждут. Ручной деплой по SSH не запускать, пока в Actions уже идёт/ждёт `deploy-vps`.

На VPS ~2 GiB RAM нужен **swap ≥2 GiB** (`/swapfile`), иначе `npm ci` / `next build` часто падают с **exit 137**. Скрипт деплоя ограничивает Node (`NODE_OPTIONS=--max-old-space-size=768`) и не гоняет `npm ci`, если `package-lock.json` не менялся.

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
.\scripts\auto_commit_push.ps1 -Message "исправить: …"
```

Cursor hook: после `stop` агента вызывается `.cursor/hooks/auto-commit-push.ps1` (см. `.cursor/hooks.json`).

Сообщение коммита:
- если `-Message` не задан → `scripts/compose_commit_message.py`
- сначала ИИ (Yandex/OpenAI из `.env`): **заголовок + тело** на русском (что/зачем)
- иначе развёрнутая эвристика по файлам/diff
- шаблон `AUTO: agent stop …` больше не используется

Не коммитит `.env` (gitignore + проверка индекса).

## 4. DNS (reg.ru)

Домен: `proverkastaza.ru`. IP VPS: **`91.229.11.147`**.  
Полная таблица (алиасы): [ops/dns-proverkastaza.md](ops/dns-proverkastaza.md).

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `91.229.11.147` |
| A | `api` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |
| A | `cabinet` | `91.229.11.147` |
| A | `admin` | `91.229.11.147` |

SSL: Let's Encrypt (certbot). Для MAX webhook нужен **валидный HTTPS**.

## 5. Apache (на нашем VPS — не nginx)

Порты 80/443 заняты Apache. Конфиги в репозитории:

- `docs/apache-vhost-proverkastaza.ru.conf` → `/var/www/taxi-doroga-dobra`
- `docs/apache-vhost-api.proverkastaza.ru.conf` → proxy на `127.0.0.1:8011`
- `docs/apache-vhost-cabinet.proverkastaza.ru.conf` → Next.js `127.0.0.1:3001`
- `docs/apache-vhost-admin.proverkastaza.ru.conf` → Next.js `127.0.0.1:3002`
- `docs/apache-vhost-redirect-aliases.conf` → 301 с алиасов и старого корня

systemd units кабинетов: `docs/systemd/sfrfr-cabinet.service`, `docs/systemd/sfrfr-admin.service`.

После `a2ensite` + `certbot --apache` появляются `*-le-ssl.conf` (HTTPS + redirect).

```apache
# api.proverkastaza.ru (эскиз HTTP; SSL добавляет certbot)
<VirtualHost *:80>
    ServerName api.proverkastaza.ru
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8011/
    ProxyPassReverse / http://127.0.0.1:8011/
</VirtualHost>
```

```apache
# proverkastaza.ru — витрина (DocumentRoot)
<VirtualHost *:80>
    ServerName proverkastaza.ru
    ServerAlias www.proverkastaza.ru
    DocumentRoot /var/www/taxi-doroga-dobra
    <Directory /var/www/taxi-doroga-dobra>
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>
```

```apache
# cabinet / admin — reverse proxy на Next.js
# cabinet → :3001, admin → :3002 (см. docs/apache-vhost-*.conf)
```

## Env на VPS

Файл `/opt/sfrfr/.env` (заполнить ключи; сервис уже слушает `127.0.0.1:8011`):

```env
PUBLIC_BASE_URL=https://api.proverkastaza.ru
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

- Витрина: https://proverkastaza.ru/ → `/var/www/taxi-doroga-dobra` (WP ru_RU, тема **Astra** + **Spectra**).
- Админ: https://proverkastaza.ru/wp-admin/ — логин/пароль в `/root/.sfrfr-secrets/wp-taxi-doroga-dobra.env` на VPS.
- Стек (в репо GitHub): `scripts/wp_install_stack.sh`
  - Astra + Spectra (без Elementor);
  - WPForms Lite (заявки; **не** сканы ПДн);
  - Rank Math SEO, UpdraftPlus, Wordfence, **WP Super Cache** (Apache);
  - не ставим: LiteSpeed Cache, Really Simple SSL (SSL уже certbot).
- Сид ТЗ-02: `scripts/wp_seed_site_tz02.sh` (обёртка `scripts/wp_seed_landing.sh`) — главная, оферта, политика ПДн, согласие, меню, CTA MAX, WPForms-лид.
- Дизайн главной: `scripts/assets/sfrfr-home.html` + `scripts/assets/sfrfr-landing.css` (синий `#1E4E79`, акцент `#2E7D5B`, Manrope).
- Форма лида: `scripts/wp_ensure_lead_form.php` (имя, телефон/канал, согласие; без файлов и СНИЛС; entries + email admin).
- Страницы: `/`, `/oferta/`, `/politika-pdn/`, `/soglasie/` (HTTPS).
- Мини-приложение MAX (`/app/`): **не клиентский кабинет** (заглушка с 2026-08-26) — `web/max-miniapp/`, выкладка `scripts/deploy_max_miniapp.sh`. ЛК клиента — только `cabinet.proverkastaza.ru`.
- В кабинете партнёра MAX URL мини-приложения может оставаться `https://proverkastaza.ru/app/` (технический); бот **не** предлагает его как ЛК.
- Диплинк чата: `https://max.ru/id8905998693_1_bot` (`MAX_PUBLIC_BOT_URL` / `MAX_CHAT_URL`) — подставить в кнопку на лендинге WP.
- API MVP (legacy `/app/`): `POST /api/cases/open`, … — не продуктовый клиентский ЛК.
- API кабинетов (JWT): `GET /api/portal/me/cases`, …; staff — `PATCH /api/portal/admin/cases/{id}/pipeline-status`.
- Next.js кабинеты: `apps/cabinet` → `cabinet.proverkastaza.ru`, `apps/admin` → `admin.proverkastaza.ru` (Apache proxy + systemd).
- На VPS нужен **Node.js ≥20.9** (факт: Node 22 LTS). Units: `sfrfr-cabinet` (:3001), `sfrfr-admin` (:3002). SSL: общий сертификат Let's Encrypt на оба хоста.
- После миграций Supabase выдать staff-роль (первый admin через CLI, service role):
  `sfrfr staff-grant --email you@company.com --role admin --invite`
  Список: `sfrfr staff-list`. Дальше роли можно править в UI admin → «Роли».
- CORS: `CORS_ALLOWED_ORIGINS` в `.env` (витрина + cabinet + admin).
- Для корректной работы MAX API нужны сертификаты Минцифры в `certs/` (см. `sfrfr.integrations.max.ssl_context`).
- Webhook API: `https://api.proverkastaza.ru/api/integrations/max/webhook` (`PUBLIC_BASE_URL` на VPS). Подписка: `sfrfr max-subscribe` после заполнения `MAX_BOT_TOKEN`.
- ПДн-сканы не через WP-формы; предпочтительно веб-кабинет; вложения в чат MAX — принимаем.
- `service_role` только на сервере API, не в JS.
