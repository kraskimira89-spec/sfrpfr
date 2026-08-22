# Staff roles: безопасные операции (P0)

## Что сделано

- Список сотрудников без UUID в основной таблице
- Приглашение по e-mail (статус `invited`, TTL 72ч)
- Запрет менять себе роль/статус
- Защита последнего активного `admin`
- Журнал `staff_access_audit`
- Legacy `PUT /admin/staff-roles/{uuid}` только для существующего сотрудника (с guards)

## Миграция

Файл: `supabase/migrations/20260822200000_staff_roles_safe_ops.sql`

```bash
# локально / CI — ваш обычный путь применения миграций Supabase
supabase db push
# или через dashboard SQL
```

Rollback (осторожно):

```sql
drop table if exists public.staff_access_audit;
alter table public.staff_roles
  drop column if exists status,
  drop column if exists display_name,
  drop column if exists invited_at,
  drop column if exists invite_expires_at,
  drop column if exists invite_token_hash,
  drop column if exists suspended_at,
  drop column if exists last_sign_in_at;
```

## API

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/portal/admin/staff` | Список |
| POST | `/api/portal/admin/staff/invites` | Приглашение |
| POST | `/api/portal/admin/staff/invites/{id}/revoke` | Отзыв |
| PATCH | `/api/portal/admin/staff/{id}` | Роль/статус |
| GET | `/api/portal/admin/staff/{id}/audit` | Журнал |
| PUT | `/api/portal/admin/staff-roles/{id}` | Legacy смена роли |

Назначение `admin` требует `confirm_admin_grant: true`.

## Роли P0

`operator` / `expert` / `admin` (UI: Оператор приёма / Специалист / Администратор).

Расширенная модель (manager, finance_admin, observer) — отдельный этап P1.
