# История проекта SFRFR

## 2026-07-23 (MAX: ответы в личку по user_id)

- Входящие шли на webhook VPS, но бот молчал: `chat_id` не читался из `message.recipient`, а личные сообщения слались неверно.
- Исправлено: `POST /messages?user_id=...`; handler читает `recipient.chat_id`; тесты обновлены.
- Доп. причина молчания на VPS: `PermissionError` на `/tmp/sfrfr-ca-bundle.pem` (файл от root). CA-бандл пишется в `/opt/sfrfr/var/` или uid-специфичный путь.

## 2026-07-22 (MAX mini-app кабинет v1)

- Статика: `web/max-miniapp/` → `https://taxi-doroga-dobra.ru/app/`.
- API: `POST /api/cases/open` + CORS с витрины; upload/status/run из кабинета.
- Бот: отображаемое имя «Стаж и пенсия», технический username `id8905998693_1_bot`; диплинк `https://max.ru/id8905998693_1_bot?startapp`.
- В кабинете партнёра MAX нужно вручную вставить URL мини-приложения.

## 2026-07-23 (ТЗ-02: лендинг + оферта + MAX)

- Сид `scripts/wp_seed_site_tz02.sh` + форма `wp_ensure_lead_form.php`.
- Страницы HTTPS: главная, `/oferta/`, `/politika-pdn/`, `/soglasie/`.
- CTA «Начать проверку» → `https://max.ru/id8905998693_1_bot?startapp`.
- WPForms id=16: имя, канал связи, согласие; без file/СНИЛС.
- Меню SFRFR Primary + Footer на Astra.

## 2026-07-22 (WP стек витрины)

- Установлено: Astra + Spectra, WPForms Lite, Rank Math, UpdraftPlus, Wordfence, WP Super Cache.
- Скрипт: `scripts/wp_install_stack.sh` (в GitHub-репо); на VPS в `/opt/sfrfr/scripts/`.
- Не ставили: Elementor, GeneratePress, LiteSpeed Cache, Really Simple SSL (SSL уже есть).

## 2026-07-22 (MAX webhook подключён)

- `MAX_BOT_TOKEN` синхронизирован на VPS; `bot_configured=yes`.
- TLS к `platform-api2.max.ru`: добавлены CA Минцифры в `certs/` + `ssl_context.py`.
- `sfrfr max-subscribe` → success на `https://api.taxi-doroga-dobra.ru/api/integrations/max/webhook`.
- `MAX_PUBLIC_BOT_URL` = `https://max.ru/id8905998693_1_bot?startapp` (технический username из `/me`).
- Кнопка на лендинге ведёт на этот диплинк (не StazhIPensiyaBot).

## 2026-07-22 (MAX бот прошёл модерацию)

- Чат-бот «Стаж и пенсия» прошёл модерацию MAX — готов к разработке.
- Следующее: `MAX_BOT_TOKEN` + публичная ссылка бота → sync на VPS → `sfrfr max-subscribe` → кнопка на лендинге.

## 2026-07-22 (шаг 2: Apache + SSL)

- DNS OK: `@` / `www` / `api` → `91.229.11.147`.
- Папка витрины: `/var/www/taxi-doroga-dobra` (заглушка index.html).
- Apache vhosts + Let's Encrypt: https://taxi-doroga-dobra.ru , https://api.taxi-doroga-dobra.ru → `8011`.
- Дальше шаг 3: WordPress в эту папку.

## 2026-07-22 (шаг 4: env API + Zakra + MAX stub)

- `/opt/sfrfr/.env`: `PUBLIC_BASE_URL=https://api.taxi-doroga-dobra.ru`, `APP_ENV=production`.
- `MAX_BOT_TOKEN` пуст → `max-subscribe` пропущен; max health: `bot_configured=no`, webhook URL корректный.
- WP: тема Zakra, главная page_id=7 — SFRFR + CTA «Написать в MAX (скоро)» (`#`).
- Сид: `scripts/wp_seed_landing.sh`; аватар в медиатеке; `MAX_PUBLIC_BOT_URL` в `.env.example`.

## 2026-07-22 (шаг 3: WordPress)

- WP ru_RU в `/var/www/taxi-doroga-dobra`, сайт «SFRFR».
- Учётки/БД: `/root/.sfrfr-secrets/wp-taxi-doroga-dobra.env` (только root).
- Админка: https://taxi-doroga-dobra.ru/wp-admin/ (user `sfrfr_admin`).

- Домен витрины SFRFR: **https://taxi-doroga-dobra.ru/** (reg.ru); API: `api.taxi-doroga-dobra.ru`.
- Сайт = посадочная/витрина SFRFR; папка на VPS отдельно от `/opt/sfrfr`.
- VPS IP: **91.229.11.147**; DNS A: `@`, `www`, `api` → этот IP.
- План по очереди: 1) DNS → 2) nginx+SSL+папка → 3) WordPress → 4) связка с API.

## 2026-07-22 (дополнение)

- Автокоммит/пуш: `scripts/auto_commit_push.ps1` + Cursor hook `.cursor/hooks.json`.
- Автодеплой на VPS `/opt/sfrfr`: `scripts/vps_bootstrap.sh`, `scripts/vps_deploy.sh`, `.github/workflows/deploy-vps.yml`.
- Миграция Supabase B2C + RLS: `supabase/migrations/20260722122128_b2c_schema_rls.sql`.

- Добавлены зависимости, `.env.example`, `.gitignore`, `docker-compose.yml`.
- Установлены agent skills: `supabase`, `supabase-postgres-best-practices`.
- Выполнен `supabase init` — появилась папка `supabase/` с `config.toml`.
- Репозиторий подключён к GitHub: https://github.com/kraskimira89-spec/sfrpfr (ветка `main`, initial commit).
- Подготовлен комплект B2C-ТЗ: монетизация, journey, архитектура данных/RLS, черновики оферты и индивидуального заказа; CRM Taganay; success fee 10% ЕДВ + 50%×3 мес.; постоплата через 2–3 мес.; эскалация при молчании 6 мес.
- Автокоммит/пуш (`scripts/auto_commit_push.ps1` + Cursor hook), автодеплой на VPS `/opt/sfrfr`, миграция Supabase B2C+RLS.
- Цель MVP: карточка дела → загрузка документов → OCR → сверка ИЛС/трудовой → черновик заявления.
- Каркас AI: `CaseStatus`, `CaseOrchestrator`, агенты classifier/extractor/drafter, RAG stub, `knowledge/`.
- Связка API/CLI: upload → local storage → OCR в `advance`/`run`, in-memory `CaseStore`.
- Решение каналов: диалог клиента в **MAX**; LLM через **Yandex AI Studio** (OpenAI-compatible).
- Каркас: `LLMClient` (yandex), `integrations/max` + webhook, деплой WP+API на VPS (`docs/deploy-vps.md`).
