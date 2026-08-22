# 2026-08-22 — Staff roles P0 (безопасный UI)

## Решение

Тестовый upsert роли по UUID заменён на:

1. Таблицу сотрудников (имя, e-mail, роль, статус, последний вход) без UUID в списке
2. Приглашения по e-mail со статусом `invited`
3. Server-side запрет самоизменения роли
4. Запрет понижения последнего активного admin
5. Журнал `staff_access_audit`

## Файлы

- `supabase/migrations/20260822200000_staff_roles_safe_ops.sql`
- `src/sfrfr/db/staff_access.py`
- `src/sfrfr/api/routes/admin_portal.py` (эндпоинты `/admin/staff*`)
- `apps/admin/src/components/staff-roles-panel.tsx`
- `docs/ops/staff-roles-safe-ops.md`
- `tests/unit/test_staff_access_guards.py`

## Не в scope

MFA / four-eyes, 6 ролей, сброс сессий Supabase.
