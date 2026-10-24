# supabase2: доступ агента (2026-10-24)

## SoT

| Поле | Значение |
|---|---|
| DNS / API | `https://supabase2.proverkastaza.ru` |
| DB-VM | `194.67.116.168` |
| Postgres | `:5433` (снаружи закрыт; локально `127.0.0.1:15433` через OpenSSH `-L`) |
| MCP | `user-supabase-selfhost` / source id `sfrfr_yc` (имя legacy) → env `SSH_HOST=194.67.116.168` |
| Режим SQL | **read-only** |

Секреты: `secrets/supabase-selfhost-mcp.env` (не в git).

## Проверка

```text
IDENTITY: db=postgres user=postgres addr=172.18.0.4/32 ver=17.6
public tables: 47
GoTrue /auth/v1/health: OK (v2.196.0) с anon key
auth.users: 189
staff_document_check_jobs: needs_action=4
fiscal migrations: 20261023180000 + 20261023190000 applied
try_fiscal_reconcile_lease: present
```

## Границы

| Контур | Назначение |
|---|---|
| **supabase2** | прод SoT: Auth, REST, payments, staff jobs — только безопасные read/smoke |
| **precheck harness** `:55432` | одноразовый Docker для TRUNCATE/isolation; **не** supabase2 |

Не делать на supabase2: `TRUNCATE`, смену маркеров isolation, live MAX без OK, удаление данных.

## Browser / staff JWT

Блокер «нет GoTrue» относится к **локальному** precheck-стенду. На supabase2 GoTrue **есть**.  
Для admin E2E нужны staff credentials / OTP на **тестовом** аккаунте — не invent login в прод без владельца.

## MCP после смены SoT

Если Cursor MCP писал `SOURCE_UNREACHABLE` / `sfrfr_yc`:

1. Убедиться, что `secrets/supabase-selfhost-mcp.env` → `SSH_HOST=194.67.116.168`
2. Порт `15433` LISTENING (туннель)
3. Reload MCP `supabase-selfhost` в Cursor
