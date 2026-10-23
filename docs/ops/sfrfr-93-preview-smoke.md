# SFRFR-93: preview / prod smoke (до merge #247)

Миграция: `supabase/migrations/20261023180000_payments_fiscal_reconcile_attempts.sql`

**Целевая БД (канон после SFRFR-73):** supabase2 на reg.ru  
`194.67.116.168` / `https://supabase2.proverkastaza.ru`  
(копия/cutover с YC; app `91.229.11.147` → этот SoT).

Применение: SSH на **DB-VM** supabase2 → `docker compose exec` + роль
`supabase_admin` (роль `postgres` не owner `payments`). Реестр:
`sfrfr_ops.schema_migrations`. App-VPS миграции **не** применяет.

YC VM C — только если снова станет SoT; сейчас при недоступном Яндексе smoke
делается на supabase2.

Auto-merge **не** включать, пока этот чек-лист не зелёный.

## 1. Миграция + RPC

```sql
-- колонки
SELECT column_name FROM information_schema.columns
WHERE table_schema='public' AND table_name='payments'
  AND (column_name LIKE 'reconcile%' OR column_name = 'last_reconcile_at')
ORDER BY 1;

-- lease: второй вызов 0 строк (подставить реальный payments.id)
SELECT id FROM try_fiscal_reconcile_lease('PAYMENT_UUID'::uuid, 120);
SELECT id FROM try_fiscal_reconcile_lease('PAYMENT_UUID'::uuid, 120);  -- empty

-- TTL у границы: выставить reconcile_post_at и смотреть fiscal_reconcile_ttl_alive
SELECT fiscal_reconcile_ttl_alive('PAYMENT_UUID'::uuid);

-- claim: второй раз пусто
SELECT id FROM claim_fiscal_reconcile_alert('PAYMENT_UUID'::uuid);
SELECT id FROM claim_fiscal_reconcile_alert('PAYMENT_UUID'::uuid);
```

## 2. Два параметра `or` (PostgREST)

Из API/сервис-роли (или curl к `/rest/v1/payments`) выполнить тот же chain, что
`list_succeeded_payments_for_reconcile`, и в access-log / DevTools убедиться:
`?or=(fiscal_status...)&or=(and(paid_at...))` — **два** `or`.

Контроль: строка `status=succeeded`, `fiscal_status=registered`, `paid_at` в окне
**не** должна попасть в результат.

## 3. Dry-run tick

До и после тика — один снимок (без PII; подставьте id кандидата или `LIMIT 20`):

```sql
SELECT id,
       last_reconcile_at,
       reconcile_attempts,
       reconcile_pre_error_streak,
       reconcile_post_at,
       (reconcile_post_payload IS NOT NULL) AS has_payload,
       reconcile_last_outcome,
       reconcile_alerted_at
FROM public.payments
WHERE status = 'succeeded'
  AND provider_payment_id IS NOT NULL
ORDER BY last_reconcile_at DESC NULLS LAST
LIMIT 20;
```

```bash
# на preview / VPS с preview DATABASE_URL
FISCAL_RECONCILE_ENABLED=1
FISCAL_RECONCILE_DRY_RUN=1
FISCAL_RECONCILE_ALERT_SINCE=2026-10-23T00:00:00+00:00

python -m sfrfr fiscal-reconcile-tick
```

Повторите SQL. Ожидание: лог «создал бы…»; изменился только `last_reconcile_at`;
`reconcile_attempts` / streak / `has_payload` / `reconcile_alerted_at` / outcome —
как до тика. Create к ЮKassa не было.

## 4. После smoke

1. Squash-merge #247 (auto-merge вручную).
2. Timer на prod: только после логов dry-run и выбранного `ALERT_SINCE`;
   в `.env` строго `FISCAL_RECONCILE_ENABLED=1` (не `true`).
