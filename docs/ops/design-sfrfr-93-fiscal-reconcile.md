# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev2: замечания Стратега к PR #238).
Источник: разбор Стратега по `main` + пути в репо.
Код **не** стартовать без команды владельца («делаем SFRFR-93»).

## Цель

Тонкая обёртка над уже существующими `ensure_payment_receipt`, `payment_receipt_retry_gate`, `should_auto_retry_fiscal_receipt` — не новая логика фискализации.

## Три ловушки (канон)

1. **Пустой `receipt_registration`.** `ensure` пропускает только `succeeded`/`pending`; при пустом идёт к `GET /receipts` и может создать чек. Job **обязан** до вызова ensure проверить `should_auto_retry_fiscal_receipt(reg)` (истина только для `canceled`/`cancelled`) — иначе риск дубля как FD 777+778.
2. **`canceled` ≠ «чека нет».** После фискализации поле может остаться `canceled` (FD 770/771); решающий фильтр — gate по списку чеков внутри ensure.
3. **`Idempotence-Key` сейчас `uuid4` в `_post`.** Параллельные тики = два чека. Для reconcile нужен детерминированный ключ (`reconcile:{payment_id}:{attempt}`) + блокировка на платёж.

## Алгоритм (согласован)

Для кандидата: предфильтр БД → окно 48 ч / grace ≥2 мин → lock → backoff/attempts → `fetch_payment` → `should_auto_retry_fiscal_receipt` → иначе skip → `ensure_payment_receipt` (email/phone как webhook) → запись попытки → после 48 ч без succeeded receipt — алерт владельцу.

Флаг по умолчанию: `FISCAL_RECONCILE_ENABLED=0`. Первый этап — **dry-run** (лог «создал бы»), без `create_receipt`. Период: **каждые 10 мин**, отдельный systemd timer (не смешивать с `finance-due-tick`).

## Пути в коде (ответы на допущения)

| Вопрос | Ответ |
|--------|--------|
| Где платежи | Таблица `public.payments` (миграции `supabase/migrations/20260722122128_b2c_schema_rls.sql`, `…_payments_one_active_per_order.sql`). Поля: `status`, `provider_payment_id`, `paid_at`, `created_at`, `fiscal_status`, `order_id`. |
| Предфильтр `fiscal_status` | Колонка **есть и пишется**: webhook ставит `fiscal_status="registered"`, если в событии `fiscal` truthy (`payments.py` → `apply_provider_payment`). Кандидаты reconcile: `status=succeeded` и `fiscal_status IS DISTINCT FROM 'registered'` (плюс окно по `paid_at`). Это **дешёвый** отсев; решающий фильтр всё равно YK `reg` + gate. Не полагаться на `fiscal_status` как на «чека точно нет». |
| Как достать за 48 ч | Готового list-by-window **нет**. Нужен метод `list_succeeded_payments(since, until)` в `src/sfrfr/db/case_repository.py`: `status=succeeded` + `paid_at` (fallback `created_at`) + непустой `provider_payment_id` + предфильтр `fiscal_status`. |
| Email/телефон | Как webhook: `_retry_fiscal_receipt` в `src/sfrfr/api/routes/payments.py` → `get_case_row` → `clients.email` / `phone`. |
| CLI retry | `yookassa-retry-receipt` в `src/sfrfr/cli/main.py` (~1023). Логику ensure **не дублировать**. |
| Ensure / gate | `src/sfrfr/integrations/payments/__init__.py`. |
| Таймер finance | `docs/systemd/sfrfr-finance-due.timer` → `finance-due-tick`. Reconcile — **отдельные** `sfrfr-fiscal-reconcile.timer` + CLI `fiscal-reconcile-tick`. |
| Тесты эталон | `tests/unit/test_yookassa.py`. |

## Открытые решения реализации (rev2)

### 1. Хранение попыток — миграция Supabase (явно)

Алгоритм требует «запись попытки»; места в схеме сейчас **нет**.

**Канон для первой реализации:** колонки на `public.payments` (не отдельная таблица):

```text
supabase/migrations/<timestamp>_payments_fiscal_reconcile_attempts.sql
  + reconcile_attempts  int  not null default 0
  + last_reconcile_at   timestamptz null
```

- RLS/grants: те же роли, что уже пишут `payments` (service role API); отдельный grant не расширять на anon.
- Альтернатива (отложить): таблица `payment_fiscal_reconcile_attempts` — только если понадобится история каждой попытки, а не счётчик.

### 2. Блокировка — механизм

Через PostgREST/`supabase-py` **нет** прямого `FOR UPDATE SKIP LOCKED` и advisory lock без RPC.

**Канон:** lease через колонки (тот же migration):

1. `UPDATE payments SET last_reconcile_at = now(), reconcile_attempts = reconcile_attempts + 1
   WHERE id = $id AND (last_reconcile_at IS NULL OR last_reconcile_at < now() - interval 'N minutes')
   RETURNING *`
2. Если 0 rows — skip (другой воркер держит lease / backoff).
3. N = минимальный backoff между попытками (например 2 мин для первой волны).

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC-функции в миграции. Если lease окажется слаб — follow-up: `CREATE FUNCTION … FOR UPDATE SKIP LOCKED` + вызов через `.rpc()`.

### 3. TTL Idempotence-Key ЮKassa — чек-лист реализации

Открытый пункт до кода:

- [ ] Сверить TTL ключа идемпотентности в [доке ЮKassa](https://yookassa.ru/developers/using-api/interaction-format#idempotence) (обычно 24 ч — **проверить**).
- [ ] Ключ `reconcile:{yk_payment_id}:{attempt}` не переиспользовать после истечения TTL без инкремента `attempt`.
- [ ] Прокинуть ключ в `create_receipt` / `_post` только для пути reconcile (webhook/CLI ручной retry могут остаться на uuid4 **или** тоже детерминироваться отдельно — решить в том же PR, не смешивать без нужды).

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция попыток + `list_succeeded_payments` (с предфильтром `fiscal_status`).
2. Job/service в **dry-run** (`FISCAL_RECONCILE_ENABLED=0` / флаг dry-run).
3. CLI `fiscal-reconcile-tick` + systemd timer/service.
4. Тесты 1–8 (+ lease / пустой `reg`).
5. Документ в `docs/yookassa-setup.md`.

## Тесты (минимум)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip `succeeded_payment_receipt_exists`  
3. `reg=pending` → skip  
4. `reg` пустой → skip, create **не** вызывается  
5. Два тика подряд → 1 чек (lease + backoff + idem key)  
6. Вне окна 48 ч / младше grace → skip  
7. Ошибка `list_receipts` → попытка записана, create нет  
8. Исчерпаны попытки → алерт, не бесконечный цикл  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»** (или эквивалент). До неё — только этот дизайн + Tracker.
