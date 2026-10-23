# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev3: lease / счётчик / Idempotence-Key — замечания Стратега к #239).
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

## Решения реализации (rev2 + rev3)

### 1. Хранение попыток — миграция Supabase (явно)

Алгоритм требует «запись попытки»; места в схеме сейчас **нет**.

**Канон для первой реализации:** колонки на `public.payments` (не отдельная таблица):

```text
supabase/migrations/<timestamp>_payments_fiscal_reconcile_attempts.sql
  + reconcile_attempts  int  not null default 0
  + last_reconcile_at   timestamptz null
```

- RLS/grants: те же роли, что уже пишут `payments` (service role API); отдельный grant не расширять на anon.
- `DEFAULT 0` / `NULL` — существующие строки не блокируются; миграция **additive** (только ADD COLUMN).
- Перед apply на прод: прогнать на копии / Supabase preview branch (коммит 1 — самый рискованный).
- Альтернатива (отложить): таблица истории попыток — только если нужен audit каждой строки.

### 2. Lease и счётчик (rev3 — канон)

Через PostgREST/`supabase-py` **нет** прямого `FOR UPDATE SKIP LOCKED` / advisory lock без RPC.

**Время:** во всех условиях lease/backoff использовать **`now()` базы**, не `datetime.now()` из Python (записать в код-ревью чек-лист).

**Взятие lease** — только штамп, **без** инкремента попыток:

```sql
UPDATE payments
SET last_reconcile_at = now()
WHERE id = $id
  AND (
    last_reconcile_at IS NULL
    OR last_reconcile_at < now() - make_interval(secs => $lease_secs)
  )
RETURNING *;
```

- 0 rows → skip (другой воркер / ещё в lease).
- **`$lease_secs` ≥ HTTP timeout клиента** (сейчас `httpx` timeout **30 с** у ЮKassa) с запасом: канон v1 = **120 с**. Один таймер раз в 10 мин → риск гонки двух тиков мал; 120 с закрывает «ensure дольше N».
- Отдельное поле `reconcile_lease_until` в v1 **не** вводим: при одном воркере хватает `last_reconcile_at` + `lease_secs`. Follow-up — если появятся параллельные воркеры.

**Инкремент `reconcile_attempts`** — только когда реально зовём `create_receipt` **или** после ошибки сети/`list_receipts`/`create`, из‑за которой нужна новая попытка:

| Исход после lease | `reconcile_attempts` | `last_reconcile_at` |
|-------------------|----------------------|---------------------|
| skip: `reg` пустой / pending / не canceled | **не** трогать | уже обновлён при lease |
| skip: gate (чек уже есть) | **не** трогать | уже обновлён |
| dry-run «создал бы» | **не** трогать | уже обновлён |
| вызов `create_receipt` (до HTTP) | **+1** (и это число → в Idempotence-Key) | уже обновлён |
| ошибка сети / list до create | **+1** (фиксируем «потратили» попытку диагностики) **или** отдельный счётчик — канон: **+1**, чтобы не крутить бесконечно | уже обновлён |

Иначе лимит попыток съедят «пустые» тики (пустой/`pending` reg), а чек так и не создастся.

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC. Follow-up: RPC + `FOR UPDATE SKIP LOCKED`.

### 3. Idempotence-Key (rev3)

Ключ: `reconcile:{yk_payment_id}:{attempt}`, где **`attempt` = значение `reconcile_attempts` после инкремента и до HTTP** (то, что уже в БД).

| Сценарий | Поведение |
|----------|-----------|
| Сбой сети после POST, повтор с **тем же** `attempt` | ЮKassa вернёт прежний ответ — **желательно** (не второй чек) |
| Первый create завершился `canceled` / нужен новый чек | Сначала **новый** инкремент → новый `attempt` → новый ключ; иначе ЮKassa может отдать старый canceled |
| TTL ключа истёк | Не слать тот же ключ; инкремент `attempt` обязателен |

Чек-лист до кода:

- [ ] Сверить TTL в [доке ЮKassa](https://yookassa.ru/developers/using-api/interaction-format#idempotence) (часто 24 ч — **проверить**).
- [ ] Прокинуть ключ в `create_receipt` / `_post` **только** для пути reconcile (webhook / ручной CLI — uuid4 или отдельное решение в том же PR).

### 4. Тесты на ключ (добавить к 1–8)

9. Повтор после сетевой ошибки с тем же `attempt` → один логический create (тот же Idempotence-Key).  
10. После `canceled` receipt → инкремент `attempt` → **новый** ключ (не залипаем на старом ответе).

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция попыток (на preview/копии) + `list_succeeded_payments` (предфильтр `fiscal_status`).
2. Job/service в **dry-run** (`FISCAL_RECONCILE_ENABLED=0` / флаг dry-run); lease без инкремента; инкремент только у create/ошибки.
3. CLI `fiscal-reconcile-tick` + systemd timer/service.
4. Тесты 1–8 + 9–10 (lease, пустой `reg`, два сценария ключа).
5. Документ в `docs/yookassa-setup.md`.

## Тесты (минимум)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip `succeeded_payment_receipt_exists`  
3. `reg=pending` → skip (**без** роста `reconcile_attempts`)  
4. `reg` пустой → skip, create **не** вызывается (**без** роста attempts)  
5. Два тика подряд → 1 чек (lease + backoff + idem key)  
6. Вне окна 48 ч / младше grace → skip  
7. Ошибка `list_receipts` → попытка учтена (+1), create нет  
8. Исчерпаны попытки → алерт, не бесконечный цикл  
9. Сеть: тот же `attempt` → тот же Idempotence-Key  
10. После canceled receipt → новый `attempt` / новый ключ  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»** (или эквивалент). До неё — только этот дизайн + Tracker.
