# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev4: граница до/после POST create — замечание Стратега к rev3/#239).
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
| Как достать за 48 ч | Готового list-by-window **нет**. Нужен метод `list_succeeded_payments(since, until)` в `src/sfrfr/db/case_repository.py`: `status=succeeded` + `paid_at` (fallback `created_at`) + непустой `provider_payment_id` + предфильтр `fiscal_status`. **PostgREST:** `IS DISTINCT FROM 'registered'` для NULL — через `.or_("fiscal_status.is.null,fiscal_status.neq.registered")` (или эквивалент); на реальном клиенте проверить, что строки с `NULL` не теряются. |
| Лимит попыток | **`reconcile_attempts` max = 3** (после 3-го учтённого create/ошибки-до-POST → алерт, дальше только CLI). |
| Email/телефон | Как webhook: `_retry_fiscal_receipt` в `src/sfrfr/api/routes/payments.py` → `get_case_row` → `clients.email` / `phone`. |
| CLI retry | `yookassa-retry-receipt` в `src/sfrfr/cli/main.py` (~1023). Логику ensure **не дублировать**. |
| Ensure / gate | `src/sfrfr/integrations/payments/__init__.py`. |
| Таймер finance | `docs/systemd/sfrfr-finance-due.timer` → `finance-due-tick`. Reconcile — **отдельные** `sfrfr-fiscal-reconcile.timer` + CLI `fiscal-reconcile-tick`. |
| Тесты эталон | `tests/unit/test_yookassa.py`. |

## Решения реализации (rev2–rev4)

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

**Граница инкремента (rev4 — обязательно):**

| Момент сбоя / шага | `reconcile_attempts` | Idempotence-Key |
|--------------------|----------------------|-----------------|
| skip: пустой/`pending` reg, gate, dry-run | **не** трогать | не используется |
| ошибка **до** POST `create_receipt` (упал `fetch_payment` / `list_receipts`) | **+1** (ключ ещё не слали; лимит 3, чтобы не крутить вечно) | не использовался |
| **перед** успешным стартом POST `create_receipt` | **+1**, значение → в ключ | `reconcile:{yk_id}:{attempt}` |
| таймаут / обрыв **после** отправки POST `create_receipt` (неизвестно, создала ли ЮKassa чек) | **не** инкрементировать | **повторить тот же ключ** в пределах TTL |
| HTTP-ответ: receipt `canceled`, нужен новый чек | **+1** → новый ключ | новый attempt |
| HTTP-ответ: succeeded / pending | стоп; при succeeded можно выставить `fiscal_status=registered` | — |
| TTL ключа истёк, нужен повтор create | **+1** (старый ключ нельзя) | новый attempt |

Одной строкой канон: **таймаут или обрыв после POST `create_receipt` → попытку не инкрементировать, повторить с прежним ключом в пределах TTL.** Иначе новый ключ = второй чек (дубль как 777+778).

| Исход после lease | `reconcile_attempts` | `last_reconcile_at` |
|-------------------|----------------------|---------------------|
| skip: `reg` пустой / pending / не canceled | **не** трогать | уже обновлён при lease |
| skip: gate (чек уже есть) | **не** трогать | уже обновлён |
| dry-run «создал бы» | **не** трогать | уже обновлён |
| ошибка **до** POST create | **+1** | уже обновлён |
| старт POST create | **+1** до HTTP (→ ключ) | уже обновлён |
| таймаут **после** POST | **не** трогать | уже обновлён; retry тем же ключом |

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC. Follow-up: RPC + `FOR UPDATE SKIP LOCKED`.

### 3. Idempotence-Key (rev3 + граница rev4)

Ключ: `reconcile:{yk_payment_id}:{attempt}`, где **`attempt` = значение `reconcile_attempts` после инкремента и до HTTP** (уже в БД).

Чек-лист до кода:

- [ ] Сверить TTL в [доке ЮKassa](https://yookassa.ru/developers/using-api/interaction-format#idempotence) (часто 24 ч — **проверить**).
- [ ] Прокинуть ключ в `create_receipt` / `_post` **только** для пути reconcile (webhook / ручной CLI — uuid4 или отдельное решение в том же PR).

### 4. Тесты на ключ (добавить к 1–8)

9. Имитировать **таймаут на ответе** POST `create_receipt` (не ошибку до запроса) → повтор с **тем же** `attempt` / тем же Idempotence-Key → один логический create.  
10. После `canceled` receipt → инкремент `attempt` → **новый** ключ.

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция попыток (на preview/копии) + `list_succeeded_payments` (предфильтр `fiscal_status`, проверка NULL в PostgREST).
2. Job/service в **dry-run**; lease без инкремента; инкремент по таблице границ rev4.
3. CLI `fiscal-reconcile-tick` + systemd timer/service.
4. Тесты 1–10.
5. Документ в `docs/yookassa-setup.md`.

## Тесты (минимум)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip `succeeded_payment_receipt_exists`  
3. `reg=pending` → skip (**без** роста `reconcile_attempts`)  
4. `reg` пустой → skip, create **не** вызывается (**без** роста attempts)  
5. Два тика подряд → 1 чек (lease + backoff + idem key)  
6. Вне окна 48 ч / младше grace → skip  
7. Ошибка **`list_receipts` до POST create** → +1, create нет  
8. После **3** учтённых попыток (`reconcile_attempts >= 3`) → алерт, create не зовём  
9. Таймаут **на ответе** POST → тот же `attempt` / тот же Idempotence-Key  
10. После canceled receipt → новый `attempt` / новый ключ  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»** (или эквивалент). До неё — только этот дизайн + Tracker.
