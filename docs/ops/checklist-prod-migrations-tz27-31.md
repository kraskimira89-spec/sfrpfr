# Ops: применить миграции prod (SFRFR-17…22 + archive_prep)

**Дата:** 2026-08-23  
**Очередь:** SFRFR-17 … SFRFR-22 + новая `20260823240000_cases_archive_prep.sql`

## Список файлов (порядок)

1. `20260823180000_marketing_consents.sql` — SFRFR-17  
2. `20260823200000_*diagnosis_feedback*` (или актуальный файл feedback) — SFRFR-18  
3. secure delivery — SFRFR-19  
4. `*diagnosis_surveys*` — SFRFR-20  
5. `*diagnosis_delivery_state_machine*` — SFRFR-21  
6. `20260823230000_email_delivery_webhooks.sql` — SFRFR-22  
7. `20260823240000_cases_archive_prep.sql` — архивный блок admin

Точные имена — в `supabase/migrations/`.

## Проверка (read-only, до apply)

```powershell
.\.venv\Scripts\Activate.ps1
# DATABASE_URL из secrets (prod read-only)
python scripts/verify_prod_migrations_tz27_31.py
```

**Ревизия 2026-09-02 (вечер, self-host YC):** FUNNEL-7 — миграции TZ27–30 реально применены на `supabase.proverkastaza.ru` (ранее в schema_migrations отсутствовали; MCP-ревизия была ошибочной/другой БД). Таблицы `survey_*`, `diagnosis_feedback`, `diagnostic_results`, `secure_share_links`, `notification_jobs` — OK. Добавлен `acquaint` в check + `quality` scheduler.

**Ревизия 2026-09-02 (Supabase MCP):** миграции TZ27–31 **применены** на prod (`case_tracker_issues`, `marketing_consents`, `diagnosis_feedback`, `diagnosis_secure_delivery`, `diagnosis_surveys`, `diagnosis_delivery_state_machine`, `email_delivery_webhooks`, `cases_archive_prep`, `secure_action_links`). Verify: все 13 ожидаемых таблиц + `idempotency_key` / `archive_prep_status` — OK.

**Ревизия 2026-09-01:** таблицы TZ27–31 отсутствовали; были только `20260901*` (customer_journey, case_chat_*).

## Как применить

```powershell
# Локально / CI с доступом к prod (секреты не в git):
.\.venv\Scripts\Activate.ps1
# supabase db push  ИЛИ  скрипт проекта, если есть
```

После миграций:

```powershell
sfrfr amocrm-ensure-fields
```

Проверка:

```text
GET /api/webhooks/email/health
POST /api/portal/admin/diagnosis-surveys/due-tick
POST /api/portal/admin/notification-jobs/smtp-retry
```

Yandex SMTP env уже канон; Mailgun/SendGrid ключи **не** обязательны.

## Tracker

Закрывать SFRFR-17…22 комментарием «миграция применена» + дата после фактического apply.
