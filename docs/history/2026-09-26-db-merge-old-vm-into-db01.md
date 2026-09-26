# 2026-09-26 — слияние старой Supabase БД в db-01 и переключение VPS

## Проблема (split-brain)

- Старая ВМ `sfrfr-staging-supabase` (51.250.13.240) получала записи до 2026-09-25 16:48 UTC.
- Новая ВМ `sfrfr-supabase-db-01` (51.250.69.237) — с 2026-09-25 23:05 UTC.
- На VPS `DATABASE_URL` и `DBT_HOST` по-прежнему указывали на старую ВМ, `SUPABASE_URL` — на новую.
- UUID-ключи не пересекались; `storage.objects` совпадали.

## Что сделано

1. Бэкап новой БД до слияния: `~/backups/db01-before-merge-20260926T115257Z.dump` на db-01
   (`pg_dump -Fc` от `supabase_admin`, 86 TABLE DATA).
2. Read-only сравнение — `tools/db_merge_diff.py`.
3. Проверочный прогон в транзакции с ROLLBACK, затем COMMIT — `tools/db_merge_old_into_new.py`:

| Таблица | Добавлено |
|---|---:|
| auth.users | 8 |
| auth.identities | 8 |
| public.clients | 8 |
| public.cases | 8 |
| public.consents | 7 |
| public.checklist_items | 16 |
| public.case_messages | 85 |
| public.delivery_events | 16 |
| public.access_audit | 11 (новые id из sequence: старые 677–687 конфликтовали) |

   Дело `936be2ba…`: `b2c_status` `lead` → `consent_accepted` (в старой БД клиент дал согласие).
   Не переносились: отметки `updated_at` / `last_sign_in_at` сотрудника `8feaeb93…` (несущественно).
4. Повторное сравнение: `old_only = 0` во всех UUID-таблицах.
5. VPS `/opt/sfrfr/.env`: `DATABASE_URL`, `DBT_HOST` → 51.250.69.237 (копия `.env.bak-before-db01-*`),
   рестарт `sfrfr-api`, `sfrfr-case-chat-outbox`, `sfrfr-admin`, `sfrfr-cabinet`; `/health` 200.

## Что дальше

- Старую ВМ не удалять и SG не закрывать до решения владельца (откат).
- Права SA `terraform` на каталог `b1grtprgfugidt9u073i` — ТЗ `docs/ops/tz-yandex-assistant-sa-rights-db-01-folder.md`.
- Проверить ночной `sfrfr-dbt.timer` (05:30 МСК) на новой БД.
