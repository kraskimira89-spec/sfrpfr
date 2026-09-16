# Инциденты и rollback

> Действия при сбое платежей, миграций, API и webhook. Только runbook — не выполняет изменений сам.
> Перед любым изменением — сверка с `infrastructure-inventory.md` и `deploy-and-migrations.md`.

## Классификация инцидентов

| Категория | Признак | Первичная реакция |
|---|---|---|
| Сбой миграции | runner упал, schema/index не создалась | STOP; не повторять вслепую; снять состояние БД read-only |
| Сбой платежей `/pay` | 5xx, двойные provider-вызовы, 409 вместо оплаты | STOP; не тестировать ручным POST `/pay` |
| Сбой webhook | статусы не обновляются, `paid` не проставляется | диагностика, не менять платёжные строки |
| Сбой API/deploy | health ухудшился, сервис не active | откат к предыдущему состоянию кода |

## Общие правила реагирования

1. **Фиксировать состояние, не менять.** Сначала read-only: логи, `systemctl status`, `docker ps`, `git log`, health endpoint.
2. **Не удалять и не перезаписывать платёжные данные.** Любая «чистка» — только после разбора и согласования.
3. **Backup до изменений.** Если планируется любой откат/восстановление — сначала снять новый dump/snapshot.
4. **Один ответственный на изменение.** Параллельные ручные действия на одной VM/БД запрещены.

## Сбой payment-миграции

Миграция: `20260915090000_payments_one_active_per_order.sql`.

Признаки сбоя:

- runner `vm_supabase_apply_migrations.sh` завершился ошибкой;
- `payments.created_at` отсутствует;
- `payments_one_active_per_order_uidx` не создан;
- preflight-ошибка «active payment duplicates exist».

Действия:

1. STOP. Не запускать повторно до понимания причины.
2. Read-only проверка:
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_schema='public' AND table_name='payments';

   SELECT indexname, indexdef FROM pg_indexes
   WHERE schemaname='public' AND tablename='payments';

   SELECT order_id, COUNT(*) FROM public.payments
   WHERE lower(coalesce(status,'')) NOT IN
     ('succeeded','paid','canceled','cancelled','failed','expired','refunded')
   GROUP BY order_id HAVING COUNT(*) > 1;
   ```
3. Если preflight показал active-дубли → **ручное разрешение**, без автоудаления: показать список `order_id`/статусов, согласовать решение.
4. Миграция additивная (`add column if not exists` + `create unique index if not exists`) — повторный запуск безопасен **только после** устранения дублей/причины.

## Сбой платежей `/pay` (reservation-flow)

Признаки:

- `POST /pay` возвращает 500/502;
- две активные reservation на один `order_id` (должно быть невозможно после индекса);
- неоднозначный timeout оставил reservation active, но provider мог создать платёж.

Действия:

1. STOP. Не вызывать повторно `/pay` и не создавать второй provider-платёж.
2. Проверить:
   - health `https://api.proverkastaza.ru/health`;
   - логи API (`journalctl -u sfrfr-api`);
   - статусы платежей в БД (read-only SELECT по `order_id`).
3. Если reservation active без `provider_payment_id` и без ответа провайдера — разрешается webhook'ом или ручной сверкой с ЮKassa (по `metadata.order_id`), но **не** новой попыткой оплаты.
4. Если terminal (`failed`/`canceled`) — слот свободен, клиенту разрешена новая попытка.

## Сбой webhook

Признаки:

- платёж успешно создан, но статус в БД не обновляется;
- `paid` не проставляется заказу;
- ранний webhook не привязался к reservation (reconciliation).

Действия:

1. Проверить доставку webhook (логи `/api/integrations/payments/yookassa/webhook`).
2. Проверить reconciliation-path (`_bind_reservation`): reservation с `provider_payment_id IS NULL` должна привязываться по `order_id`.
3. При расхождении — ручная сверка с ЮKassa по `provider_payment_id`/`metadata.order_id`; изменения только после согласования.

## Откат deploy API

Признаки: health/logs ухудшились после deploy.

Действия:

1. Зафиксировать текущий и предыдущий коммиты (`git log`).
2. Откат кода на VM B через `vps_deploy.sh` не подходит для отката на прошлый коммит — использовать явный checkout предыдущего SHA и перезапуск `sfrfr-api`.
3. Проверить health/logs.

## Порядок rollback миграции (только после согласования)

- `created_at` и partial unique index — additивные; штатный rollback не требует их удаления.
- Если требуется откат: снять backup, согласовать шаги, **не** автоудалять платёжные данные.
- Ответственный фиксирует шаги в changelog операций.

## Контакты/ответственные (без секретов)

- Владелец облачных аккаунтов (reg.ru / YC) — для firewall/DNS/console.
- Инженер — для БД/deploy/кода.
- Платежи (ЮKassa) — сверка только через личный кабинет провайдера, не через чат.
