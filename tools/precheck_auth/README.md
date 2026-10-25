# Изолированный Auth для browser E2E (SFRFR-111)

**Не production.** Не использовать пользователей/секреты supabase2.

Цель: штатный вход admin (OTP / magic link) → JWT → API → кнопка проверки.

## Состав

| Сервис | Порт | Назначение |
|---|---|---|
| `precheck-auth-db` | 55434 | Postgres только для GoTrue (`auth` schema) |
| `precheck-gotrue` | 9999 | GoTrue API (`/auth/v1`) |
| `precheck-inbucket` | 9000 UI / 2500 SMTP | почта OTP без внешнего SMTP |

JWT secret и anon/service keys — **только** local test values в `up.ps1` / `.env.example` (не из prod).

## Запуск

```powershell
.\tools\precheck_auth\up.ps1
# выставит PRECHECK_AUTH_URL, PRECHECK_E2E_* подсказки
```

Admin/API для E2E:

```text
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:9999
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<local anon>
# API: тот же JWT secret / URL, что GoTrue
```

Синтетический сотрудник: `staff-e2e@precheck.local` (создаёт `seed_staff_user.py`).

## Приёмка

1. OTP/magic link через Inbucket (не skip).
2. JWT принимается FastAPI `get_user`.
3. Роль staff на синтетическом деле.
4. Playwright A–G с `PRECHECK_E2E_ACCEPTANCE=1` (отсутствие Auth = **fail/BLOCKED**, не skip).

Этот стенд **не** заменяет проверку против supabase2 GoTrue в проде; для DoD #269 достаточно изолированного контура с штатным login-flow.
