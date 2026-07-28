# История проекта SFRFR

## 2026-07-28 (YC billing блокер)

- Облако `cloud-infoproverkastazaru`: баланс 0 → блок новых ресурсов / AI Studio key.
- Runbook: `docs/ops/yandex-cloud-billing-unblock.md`.

## 2026-07-28 (промпт AI Studio)

- `prompts/system/yandex-ai-studio-agent.md` — LLM / Foundation Models.

## 2026-07-28 (Yandex env + org/employee model)

- Локальный `.env`: полный блок `YANDEX_*`; модель org-mailbox vs employee Telemost в ops/secrets.
- Полный healthcheck: mail/disk/calendar/telemost ok.

## 2026-07-28 (Yandex Workspace: Диск + dual calendar)

- `YANDEX_DISK_ENABLED=true`: API disk + папка `SFRFR-ops` (без ПДн).
- Dual-write Google Calendar → Яндекс (`calendar-create --mirror-yandex`, `calendar-mirror-yandex`).
- Телемост API: create 201 на токене `SFRFR_telemost`.
- Чеклист выполнения: `docs/ops/yandex-workspace-setup.md` v1.1.

## 2026-07-28 (промпты агентов)

- `prompts/` — системные промпты Cursor; агент Yandex Cloud.

## 2026-07-28 (ops self-host Supabase YC)

- `docs/ops/supabase-selfhost-yandex-cloud.md` — развёртывание стека на Compute VM.

## 2026-07-28 (копирайт каналов)

- Success-форма и CTA лендинга: «кабинет на сайте» (не «в браузере»).

## 2026-07-27 (ТЗ-15 локализация ПДн)

- Спека `docs/specs/15-data-localization-ru.md`: целевой РФ-контур, MVP на Cloud, план миграции.
- Ссылки в README, ТЗ-01/06/07.

## 2026-07-27 (код ТЗ-14 Yandex Workspace)

- Реализованы oauth/mail/telemost/calendar; Диск off.
- Admin + CLI; `cases.meeting_url`; Telemost API требует 360 на личном ящике.

## 2026-07-27 (ТЗ-14 Яндекс Workspace)

- Спека OAuth сервисов аккаунта (почта/Телемост/календарь) отдельно от Cloud AI Studio.
- Ops: `docs/ops/yandex-workspace-setup.md`.

## 2026-07-27 (ТЗ-13 document ingest v2)

- Спроектирован ingest поверх `ocr/engine.py`: text layer → Vision/Tesseract, quality gate, HITL эксперта.
- Спека: `docs/specs/13-document-ingest-v2.md`.

## 2026-07-27 (код без Taganay)

- Удалён модуль `integrations/taganay`; env TAGANAY_*; CLI `taganay-sync`.
- Единственная CRM в коде — amoCRM (ТЗ-12).

## 2026-07-27 (документация CRM)

- Во всех ТЗ/доках CRM Taganay заменена на amoCRM; единый E2E-чеклист `docs/qa/lead-amocrm-e2e.md`.

## 2026-07-26 (ТЗ-12 amoCRM: пошаговая настройка)

- Расширен `docs/ops/amocrm-setup.md`: шаги 0–7 где кликать в амоМаркете/воронках/полях.
- `docs/specs/12-amocrm.md` ссылается на ops-инструкцию как часть ТЗ.

## 2026-07-26 (ТЗ-12 amoCRM)

- Спека `docs/specs/12-amocrm.md`; модуль `integrations/amocrm/`.
- Custom fields CASE_ID и др.; sync из public leads и admin; CLI ensure-fields/sync.
- Основная CRM — amoCRM (ТЗ-12).
- Ops: `docs/ops/amocrm-setup.md` — пошагово где кликать в амоМаркете/воронках/полях.

## 2026-07-27 (ТЗ-11 P0 дожим)

- Статьи 10–16; `#stati` на главной; comments off; chip `rodstvenniki`.

## 2026-07-26 (лендинг: меню IA)

- `wp_seed_site_tz02.sh`: меню под 8 блоков; оферта в footer; apply-скрипт `wp_apply_landing_vps.sh`.

## 2026-07-26 (лендинг: сжатие воронки)

- Короткая главная; контент → blog 05–09; sticky MAX; SVG в hero.

## 2026-07-26 (лендинг: UI-сверка)

- `sfrfr-home.html` / `sfrfr-landing.css`: пример тарифа, «Кто оказывает», MAX primary, hover, секции/24px.

## 2026-07-26 (P0/P1: блог §13, QA D, лид→amoCRM)

- `11-blog.md` восстановлен из git + §13; UI assets + MU-plugin + deploy script.
- `docs/qa/tz09-stage-d.md` — пошаговый runbook; браузерный E2E 1–5 не закрыт.
- `docs/qa/lead-amocrm-e2e.md`; ТЗ-10 P0 формы/юристы обновлены по факту smoke.
- Notion `np/` / MCP — отложено (auth недоступен).

## 2026-07-26 (хвосты cutover)

- Чеклист: `docs/ops/cutover-manual-checklist.md` (MAX URL, Supabase Auth, reCAPTCHA domains).
- Скрипт доменов reCAPTCHA: `scripts/ops_patch_recaptcha_domains.py` (SA сейчас без IAM на keys).

## 2026-07-26 (fix редиректов алиасов)

- `prostaz.ru` / `proverka-staza.ru`: после certbot отдавали default Apache; починены чистые HTTP+HTTPS 301 → `proverkastaza.ru`.
- Шаблон SSL: `docs/apache-vhost-redirect-aliases-le-ssl.conf`; cutover переустанавливает его после certbot.

## 2026-07-28 (оглавление Яндекс ID / Вебмастер / Метрика)

- `Yandex ID/` — OAuth (ТЗ-14); `Yandex Webmaster/` — индексация/sitemap; `Yandex Metrika/` — счётчик/цели без ПДн.

## 2026-07-28 (оглавление Yandex Cloud + AI Studio)

- `Yandex Cloud/` — IAM, регионы РФ, MPG/Storage/Captcha/Vision (ТЗ-15).
- `Yandex AI Studio/` — OpenAI-compatible LLM, embeddings, security, SDK.

## 2026-07-27 (оглавление документации MAX)

- Папка `MAX/`: пользовательская (business/help) и developer (API/Bridge/UI) сводки для ориентации SFRFR.

## 2026-07-27 (оглавление документации amoCRM)

- Папка `amo CRM/`: пользовательская и developer-сводки (таблицы ссылка/раздел/кратко/приоритет SFRFR).

## 2026-07-26 (хвосты cutover)

- Куплены: `proverkastaza.ru` (основной), `proverka-staza.ru`, `prostaz.ru`.
- Apache vhosts + cutover: `scripts/vps_cutover_proverkastaza.sh`, DNS: `docs/ops/dns-proverkastaza.md`.
- 301 со старого `taxi-doroga-dobra.ru` и алиасов; WP остаётся в `/var/www/taxi-doroga-dobra`.

## 2026-07-26 (dbt: Tier-1 тесты)

- Плагин dbt Labs: закрыты пробелы в `analytics/models/schema.yml`.
- Добавлен `stg_communications` (unique/not_null/relationships).
- Усилены PK/FK: `fct_success_fee`, `fct_silent_cases`; not_null в dim/mart.

## 2026-07-26 (дубль ТЗ-09)

- Удалён корневой дубль `09-client-channels-parity.md`; канон — `docs/specs/`.

## 2026-07-25 (блог: ситуации DeepSeek)

- 25 обезличенных «примеров ситуаций» + 5 аналитических (каждые 5 клиентов).
- `manifest.json` → `generate_blog_situations.py` → `wp_seed_blog_situations`.
- CASE-2026-016 (НКО) пропущен; в CASE-005 summary убраны явные ФИО.

## 2026-07-25 (блог: fix rewrite 404)

- `category_base=blog/rubrika` — иначе `/blog/slug/` статей давал 404.
- Статьи #1–#4: 200; архив `/blog/` и рубрики `/blog/rubrika/*/`: 200.

## 2026-07-25 (блог ТЗ-11 MVP на сайте)

- `/blog/` + статьи #1–#4; блок «Читайте также»; FAQ → статьи.
- `scripts/wp_seed_blog_tz11.sh|.php`, `docs/ops-blog-editor.md`.

## 2026-07-25 (ТЗ-11: блог)

- Добавлен `docs/specs/11-blog.md`: назначение, рубрики, шаблон статьи,
  12 тем P0, воронка CTA → `#kak-rabotat`, границы ПДн/обещаний.
- В `docs/specs/README.md` — ссылки на ТЗ-10 и ТЗ-11; правило хранить новые ТЗ здесь.

## 2026-07-22 (ТЗ-03/09 закрытие пробелов без SMS)

- Deep-link `/cases/{id}`; канал и «Продолжить в MAX» в «Ещё».
- Уведомления статуса: две CTA по preferred_channel (MAX + чат дела).
- Общий словарь статусов; API/UI законного представителя; QA этап D.

## 2026-07-22 (P0 UX кабинета для пенсионеров)

- Мастер одного дела: «Сейчас нужно» + шаги согласие / документы / проверка.
- Пароль после MAX — опционально («позже»); канал работы убран с главной.
- Типографика ≥18px, кнопки 56px; запасные способы входа свёрнуты.

## 2026-07-25 (логирование входа клиента)

- Logger `sfrfr.auth.portal` + `auth_event()` без ПДн.
- `RedactingFilter` больше не ломает access-логи uvicorn.
- Автосоздание `clients` при MAX session, если строки ещё нет.
- Пустые `maybe_single` → 500 на `/me` и создании дела; заменено на `limit(1)`.

## 2026-07-25 (P0 путь клиента)

- Лендинг: главные CTA → `#kak-rabotat`; «В браузере» → register через MAX.
- Кабинет: дефолт регистрация через чат MAX; пустой список → создать и открыть дело.

## 2026-07-25 (термины входа)

- Единый словарь: чат MAX / браузер / страница входа / почта.
- Кнопки: «Показать код для MAX» (страница входа) ↔ подсказка бота после «Начать»;
  «Подтвердить вход в браузере» (чат MAX).

## 2026-07-25 (nightly dbt)

- Nightly dbt запускается автономно на VPS через `sfrfr-dbt.timer` в 05:30 МСК;
  логи остаются в journald на сервере.
- Для устойчивого dbt DDL выбран direct PostgreSQL endpoint после включения
  Supabase IPv4 add-on; GitHub Actions не используется.

## 2026-07-25 (VPS + dbt)

- SSH к VPS ок: `DBT_*`, `profiles.yml`, `dbt` 1.12, `sfrfr-api` active.
- Direct Supabase с VPS только IPv6; session pooler + `dbt build` на VPS зависает (locks / futex).
- Витрины восстановлены через `psql` по одному statement; cron dbt временно выключен.
- `dbt_run.sh`: `--threads 1 --no-populate-cache`.

## 2026-07-25 (dbt: RLS на витринах)

- RLS на `analytics.*` marts через dbt post-hook (владелец `analytics_transformer`); без политик для anon/authenticated.

## 2026-07-24 (dbt: обезличенная аналитика)

- Добавлены схемы `analytics_source` и `analytics`, роль `analytics_transformer` и dbt-витрины для воронки, платежей, success fee, silent cases и управленческого дашборда.
- Контракт источников исключает ПДн, документы, тексты сообщений, внешние ID платежей и точные суммы; для денег используются диапазоны.

## 2026-07-24 (вход через MAX OTP)

- Кабинет: вкладка MAX + «Получить код в MAX»; API `POST /api/portal/auth/otp/request|verify|link`; HMAC ticket/link в `login_otp.py`; кнопка бота «Подтвердить вход в веб кабинет»; `max_chat_url` без `?startapp`.

## 2026-07-24 (Google MVP рядом с Supabase)

- **SoT:** FastAPI + Supabase. Google — вспомогательно (без дублирования дел).
- Drive + Sheets: уже были; дерево Drive / whitelist Sheets без ПДн.
- **Calendar:** `integrations/calendar`, CLI `calendar-create` / `calendar-list` (только `case_id` в событии).
- **reCAPTCHA Enterprise:** проверка на `POST /api/public/leads` при заданных ключах; WP передаёт `recaptcha_token`.
- **Search Console:** CLI `gsc-sites` (ops); Looker Studio — вручную поверх Sheets Analytics.
- Отложено: Gmail (нужен Workspace DWD), Docs/Meet/Forms/Apps Script, Vision, Secret Manager.

## 2026-07-23 (ТЗ-09: паритет MAX ↔ веб)

- Auth: `X-MAX-InitData` / (dev) `X-MAX-User-Id` → Principal; `audit_actor_id` для MAX-only.
- Portal: `POST /cases`, signed `link_token`, `GET /me/notification-links`.
- Mini-app → `/api/portal/*` (Supabase), список дел, consent, chat/pay handoff, prefs.
- Cabinet: deep-link `?case=` / `link_token`; CTA MAX с делом.
- Тесты: link token, notification order, openapi routes.

## 2026-07-23 (ТЗ-08: knowledge / RAG)

- Контур: feedback эксперта → `apply_expert_feedback` → `CASE-YYYY-NNN` (+ `.md` для verified/template).
- Admin: `POST .../knowledge-feedback` возвращает knowledge_case; `GET .../knowledge-cases`.
- Guardrail: `ensure_needs_human_review`; тесты rejected вне RAG, ASSISTANT_SYSTEM, feedback loop.
- Импорт/CLI/RAG filter verified|template — уже были; доведена петля улучшения.

## 2026-07-23 (ТЗ-07: очередность MVP)

- Этап 1: `POST /api/public/leads` (WPForms/JSON) → client+case+checklist+amoCRM; WP CTA меню → `/#kak-rabotat`; форма с выбором канала.
- MAX: `/docs`, `/draft`, скачивание вложений по URL.
- Оплаты: кнопка «Оплатить онлайн» в cabinet + fallback на ручной счёт.
- Чеклист: `docs/ops-mvp-checklist.md`; тесты `tests/integration/test_mvp_roadmap.py`.

## 2026-07-23 (ТЗ-06: интеграции и безопасность)

- amoCRM: webhook-клиент + sync по `case_id` (минимум контактов, без OCR/файлов); CLI `amocrm-sync`.
- Google Sheets: whitelist-выгрузка без ПДн; `POST /admin/analytics/sheets-sync`, CLI `sheets-sync`.
- ЮKassa: create payment + webhook → `payments`/`orders`; пути `/api/portal/.../pay` и `/api/integrations/payments/...`.
- Константы: signed URL TTL 60с, private bucket `pension-docs`; проверка frontend `.env.example` без `service_role`.
- Тесты: `tests/integration/test_tz06_security.py`, `tests/unit/test_integrations_tz06.py`.

## 2026-07-23 (cabinet/admin на VPS)

- DNS reg.ru: `cabinet` / `admin` → `91.229.11.147`.
- Apache vhost + Let's Encrypt (общий cert); systemd `sfrfr-cabinet` :3001, `sfrfr-admin` :3002.
- Node.js на VPS обновлён до **22 LTS**; HTTPS 200 на оба поддомена.

## 2026-07-23 (ТЗ-05: ops / health / CI)

- `/health` без ПДн; `/ops/status` по `X-Ops-Token`; redacting filter логов.
- CLI: `ops-health`, `ops-check-remote`; скрипты `scripts/ops_check.sh|ps1`.
- Deploy только после api+cabinet+admin; smoke curl `/health`; ранбук `docs/ops-runbook.md`.

## 2026-07-23 (Supabase: миграции + staff CLI)

- На remote Supabase накатаны: `b2c_schema_rls`, `secure_roles_case_data`, `client_channels_admin_feedback`, revoke anon EXECUTE на helpers.
- CLI: `sfrfr staff-grant --email … --role admin|expert|operator [--invite]`, `sfrfr staff-list`.
- Auth users пока пуст — первый admin создаётся через `--invite`.

## 2026-07-23 (ТЗ-04 admin + учёт ТЗ-09 каналов)

- Admin UI: дашборд, реестр (поиск/фильтры/каналы), карточка, финансы, аналитика, роли.
- API `/api/portal/admin/*` + `GET /me`; ролевые ограничения operator/expert/admin на сервере.
- Миграция: `preferred_channel`, `max_user_id`, `case_knowledge_feedback`.
- В карточке: паритет каналов MAX↔веб, amoCRM URL, audit, knowledge feedback → verified/template.

## 2026-07-23 (ТЗ-03: клиентский кабинет)

- UI `apps/cabinet`: OTP email/телефон, список дел, карточка, согласия, оплаты, результат.
- Portal API: согласия/оферта, заказы, результат + success fee, signed URL, блок upload без ПДн-согласия.
- Клиентский `GET /cases/{id}` без OCR/findings; audit на просмотр/загрузку/акцепты.
- Предупреждение «Решение принимает СФР…»; кнопки подачи в СФР от имени клиента нет.

## 2026-07-23 (инструкция ЮKassa)

- `docs/yookassa-setup.md` — шаги по [developers.yookassa](https://yookassa.ru/developers): ЛК, env, webhook, тест, чеки, бой.

## 2026-07-23 (ТЗ-09 этап C: ЮKassa + mini-app)

- ЮKassa: чек (опционально), return_channel, b2c_status после оплаты, webhook package_code.
- Mini-app: вкладки Оплаты / Результат / Сообщения + оплата онлайн.
- Cabinet: deep-link `?case=&view=payments|result`.

## 2026-07-23 (ТЗ-09 этап B: паритет операций)

- Portal: `POST .../run`, `GET .../findings|draft|checklist|documents`, `GET .../meta/status-labels`.
- Веб-кабинет: «Запустить проверку» + блок findings.
- Mini-app: чек-лист, draft, инструкция подачи; CaseRead с RU-лейблами.

## 2026-07-23 (ТЗ-09 этап A: каналы MAX/веб)

- API: `GET/PATCH /api/portal/me`, `POST /link/max`, `POST /link/web-from-max`.
- Миграция каналов уже была (`max_user_id`, `preferred_channel`).
- Бот `/start`/`/help` — выбор канала; лендинг `#kak-rabotat`; cabinet + miniapp переключатели.

## 2026-07-23 (ТЗ-09: паритет MAX и веб-кабинета)

- Спек `docs/specs/09-client-channels-parity.md`: выбор канала, матрица Must/Should, link MAX↔web, единый portal API, этапы A–D.
- Обновлены ссылки в 01/02/03/07 и README спеков.

## 2026-07-23 (все пенсионные диалоги DeepSeek)

- Импортировано 26 draft-кейсов CASE-2026-002…027 из `conversations.json`.
- Шаблон CASE-2026-001 сохранён; cleaned MD в `storage/knowledge_inbox/cleaned/`.

## 2026-07-23 (импорт DeepSeek export)

- CLI: `knowledge-import-deepseek conversations.json` — пенсионные диалоги по title.
- Пилот: CASE-2026-002…006 (draft) из экспорта; cleaned MD в `storage/knowledge_inbox/` (gitignore).
- `user.json` не импортируется (email/PII). Обезличивание усилено для фамилий.

## 2026-07-23 (пакетное обезличивание)

- CLI: `sfrfr knowledge-depersonalize-dir inbox/ --out cleaned/`.
- Модуль `batch_depersonalize`: md/txt/json/html/csv; PDF/сканы → skip.

## 2026-07-23 (база знаний RAG без дообучения)

- Спек `docs/specs/08-knowledge-rag.md`: диалоги → обезличивание → draft → эксперт → RAG.
- Код: `KnowledgeCase`, `depersonalize_text`, registry/importer, CLI `knowledge-*`.
- RAG читает только `verified`/`template`; пример `knowledge/cases/CASE-2026-001.json`.
- Промпт `ASSISTANT_SYSTEM` для AI-помощника эксперта.

## 2026-07-23 (кабинеты: env/Apache/CI после ENOSPC)

- Восстановлен корневой `.env.example` (обнулён при ENOSPC) + `CORS_ALLOWED_ORIGINS`.
- Apache vhost + systemd для `cabinet.` / `admin.`; CI собирает Next.js apps.
- Каркас: `/api/portal`, JWT/RBAC, миграция `20260723094202_secure_roles_case_data.sql`, apps/cabinet и apps/admin.
- Проверки: `ruff` + `pytest` (18), `next build --webpack` для cabinet/admin.

## 2026-07-23 (MAX: ответы в личку по user_id)

- Входящие шли на webhook VPS, но бот молчал: `chat_id` не читался из `message.recipient`, а личные сообщения слались неверно.
- Исправлено: `POST /messages?user_id=...`; handler читает `recipient.chat_id`; тесты обновлены.
- Доп. причина молчания на VPS: `PermissionError` на `/tmp/sfrfr-ca-bundle.pem` (файл от root). CA-бандл пишется в `/opt/sfrfr/var/` или uid-специфичный путь.

## 2026-07-24 (мини-приложение: компактный обзор + бургер)

- Первый экран — только текущий этап и 3 действия (загрузка / проверка / обновить).
- Всегда видимый бургер: этапы пайплайна + разделы (документы, чек-лист, черновик, оплаты, результат, сообщения).
- URL: https://taxi-doroga-dobra.ru/app/

## 2026-07-22 (MAX mini-app кабинет v1)

- Статика: `web/max-miniapp/` → `https://taxi-doroga-dobra.ru/app/`.
- API: `POST /api/cases/open` + CORS с витрины; upload/status/run из кабинета.
- Бот: отображаемое имя «Стаж и пенсия», технический username `id8905998693_1_bot`; диплинк `https://max.ru/id8905998693_1_bot?startapp`.
- В кабинете партнёра MAX нужно вручную вставить URL мини-приложения.

## 2026-07-23 (дизайн лендинга SFRFR)

- Концепция: синий `#1E4E79`, акцент `#2E7D5B`, Manrope, кнопки ≥48px.
- Секции 1–11 на главной: hero, доверие, ЦА, шаги, проверка/не обещаем, результат, тарифы, кейсы, FAQ, CTA, footer.
- CSS: `scripts/assets/sfrfr-landing.css` → WP Custom CSS; HTML: `scripts/assets/sfrfr-home.html`.

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
- Подготовлен комплект B2C-ТЗ: монетизация, journey, архитектура данных/RLS, черновики оферты и индивидуального заказа; amoCRM; success fee 10% ЕДВ + 50%×3 мес.; постоплата через 2–3 мес.; эскалация при молчании 6 мес.
- Автокоммит/пуш (`scripts/auto_commit_push.ps1` + Cursor hook), автодеплой на VPS `/opt/sfrfr`, миграция Supabase B2C+RLS.
- Цель MVP: карточка дела → загрузка документов → OCR → сверка ИЛС/трудовой → черновик заявления.
- Каркас AI: `CaseStatus`, `CaseOrchestrator`, агенты classifier/extractor/drafter, RAG stub, `knowledge/`.
- Связка API/CLI: upload → local storage → OCR в `advance`/`run`, in-memory `CaseStore`.
- Решение каналов: диалог клиента в **MAX**; LLM через **Yandex AI Studio** (OpenAI-compatible).
- Каркас: `LLMClient` (yandex), `integrations/max` + webhook, деплой WP+API на VPS (`docs/deploy-vps.md`).

## 2026-07-27
- Блог/лендинг: CTA «Задать вопрос» → MAX + форма лида; расширен FAQ.

