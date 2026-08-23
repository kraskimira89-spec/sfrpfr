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
