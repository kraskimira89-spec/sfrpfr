# Deploy и миграции

> Порядок операций для production. Ничего не выполняет сам по себе — это runbook.
> Перед любым шагом свериться с `infrastructure-inventory.md` (целевая VM подтверждена) и `production-access.md` (доступ).

## Базовый порядок rollout

1. Подтвердить целевую VM по `infrastructure-inventory.md`.
2. Убедиться, что сервер получает актуальный `origin/main` (deploy-механизм — GitHub Actions `deploy-vps.yml` для приложения; runner на ВМ для БД).
3. Сделать backup/snapshot и записать его идентификатор.
4. Выполнить read-only preflight.
5. Применить только согласованные миграции.
6. Проверить DB schema/indexes.
7. Выпустить API.
8. Проверить health, application logs и ошибки.
9. Выполнить мониторинг после deploy.
10. Зафиксировать результат в changelog операций.

## Механизмы выпуска (факты)

- **Приложение (VM B, reg.ru):** push в `main` → GitHub Actions `deploy-vps.yml` (appleboy/ssh-action) → `sudo bash /opt/sfrfr/scripts/vps_deploy.sh`:
  - `git fetch` + `reset --hard origin/main`;
  - переустановка venv, `systemctl restart sfrfr-api` + Next-кабинеты (`sfrfr-cabinet`, `sfrfr-admin`);
  - systemd units: `sfrfr-api`, `sfrfr-cabinet`, `sfrfr-admin`, `sfrfr-document-ingest`, `sfrfr-case-chat-outbox`.
- **База данных (VM C, YC):** миграции применяются **не** через GitHub Actions, а runner'ом на самой ВМ:
  - `scripts/vm_supabase_apply_migrations.sh` — `docker compose exec db psql` (контейнер `supabase-db`);
  - реестр применённых миграций: `sfrfr_ops.schema_migrations` (идемпотентно, пропускает уже применённые файлы из `supabase/migrations/`).

## Payment atomicity rollout

Миграция: `supabase/migrations/20260915090000_payments_one_active_per_order.sql`

Порядок:

1. Проверить active-дубли `payments` (preflight — см. ниже).
2. Применить миграцию (только на VM C, после backup).
3. Убедиться, что есть:
   - `payments.created_at` (timestamptz NOT NULL DEFAULT now());
   - `payments_one_active_per_order_uidx` (partial unique index).
4. Только затем выпустить API reservation-flow (deploy приложения).
5. Не тестировать production ручным `POST /pay`.

### Preflight (read-only, до миграции)

```sql
-- 1) active-дубли (если >0 — СТОП, без чистки):
SELECT order_id, COUNT(*) AS active_count, array_agg(status ORDER BY status)
FROM public.payments
WHERE lower(coalesce(status, '')) NOT IN
  ('succeeded','paid','canceled','cancelled','failed','expired','refunded')
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 2) колонка уже есть?
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'payments';

-- 3) индекс уже есть?
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'payments';
```

## Stop conditions

Немедленно остановиться, если:

- production VM не подтверждена по `infrastructure-inventory.md`;
- отсутствует backup/snapshot;
- найдены active-дубли платежей;
- migration runner не показывает точный список применяемых файлов;
- проверка schema/index не проходит;
- health/API errors ухудшаются после rollout.

## Rollback-указатели

- Детальный порядок отката и ответственные — в `incident-and-rollback.md`.
- Миграция `20260915090000_...` является additивной (`add column if not exists` + `create unique index if not exists`); откат — отдельно согласуется, без автоудаления платёжных данных.
