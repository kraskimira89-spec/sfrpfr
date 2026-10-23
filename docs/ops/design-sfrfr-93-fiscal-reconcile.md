# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev5: `reconcile_last_outcome` + алерт один раз — замечание Стратега к #240).
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
| Лимит попыток | **`reconcile_attempts` max = 3** (учтённые: create и ошибки **до** POST; в т.ч. серия `canceled`). После исчерпания → **один** алерт (см. `reconcile_alerted_at`), дальше только CLI. |
| Email/телефон | Как webhook: `_retry_fiscal_receipt` в `src/sfrfr/api/routes/payments.py` → `get_case_row` → `clients.email` / `phone`. |
| CLI retry | `yookassa-retry-receipt` в `src/sfrfr/cli/main.py` (~1023). Логику ensure **не дублировать**. |
| Ensure / gate | `src/sfrfr/integrations/payments/__init__.py`. |
| Таймер finance | `docs/systemd/sfrfr-finance-due.timer` → `finance-due-tick`. Reconcile — **отдельные** `sfrfr-fiscal-reconcile.timer` + CLI `fiscal-reconcile-tick`. |
| Тесты эталон | `tests/unit/test_yookassa.py`. |

## Решения реализации (rev2–rev5)

### 1. Хранение попыток / исхода / алерта — миграция Supabase (явно)

Алгоритм требует «запись попытки» и знание исхода **между тиками** (10 мин); места в схеме сейчас **нет**.

**Канон (вариант 1 Стратега — выбран):** additive-колонки на `public.payments`:

```text
supabase/migrations/<timestamp>_payments_fiscal_reconcile_attempts.sql
  + reconcile_attempts       int  not null default 0
  + last_reconcile_at        timestamptz null
  + reconcile_last_outcome   text null
       -- null | error_before_post | post_started | unknown_after_post
       -- | canceled | succeeded | pending | skip_* (опционально)
  + reconcile_alerted_at     timestamptz null
       -- когда ушёл алерт «исчерпаны попытки» / «48ч без чека»; повторно не слать
```

- RLS/grants: те же роли, что уже пишут `payments` (service role API); отдельный grant не расширять на anon.
- `DEFAULT 0` / `NULL` — существующие строки не блокируются; миграция **только ADD COLUMN**.
- Перед apply на прод: копия / Supabase preview branch (коммит 1 — самый рискованный).
- Вариант 2 (повтор ключа только внутри одного тика + на следующем тике новый attempt после `GET /receipts`) — **отклонён**: безопасность только на gate, риск дубля при отставании списка чеков. Не использовать без явной смены канона.
- Отдельная таблица истории попыток — отложить.

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

**Между тиками (rev5):** состояние процесса не живёт 10 минут → ветку выбирает `reconcile_last_outcome`:

| `reconcile_last_outcome` | На следующем тике |
|--------------------------|-------------------|
| `unknown_after_post` | **не** +1; POST с тем же `attempt` / тем же ключом (если TTL ещё жив); иначе см. TTL |
| `error_before_post` | обычный путь (можно новый +1 при следующей ошибке/create по таблице границ) |
| `canceled` | нужен новый create → +1 и новый ключ (если attempts < 3) |
| `succeeded` / `pending` | skip (gate / fiscal_status) |
| `null` | первый заход; обычный путь |

Перед POST при `unknown_after_post` всё равно сначала gate/`list_receipts` (тест 2): если уже есть succeeded/pending `type=payment` — skip, выставить `succeeded`/`pending`, **не** слать create. Теоретический «таймаут + два чека» ловит gate; отдельная строка в таблице границ не нужна.

**Алерт один раз (rev5):** при `reconcile_attempts >= 3` или «48 ч без succeeded receipt»:

1. Если `reconcile_alerted_at IS NULL` → отправить алерт (Tracker comment / лог+метрика), выставить `reconcile_alerted_at = now()` (БД).
2. Если уже заполнено → **не** слать повторно на каждом 10-мин тике.
3. Сброс `reconcile_alerted_at` — только вручную/CLI после разбора (не автоматически).

| Исход после lease | `reconcile_attempts` | `reconcile_last_outcome` |
|-------------------|----------------------|--------------------------|
| skip: `reg` пустой / pending / не canceled | **не** трогать | можно `skip_reg` (опц.) |
| skip: gate | **не** трогать | `succeeded` / `pending` |
| dry-run | **не** трогать | не менять / `null` |
| ошибка **до** POST create | **+1** | `error_before_post` |
| старт POST create | **+1** до HTTP | `post_started` (сразу), затем по ответу |
| таймаут **после** POST | **не** трогать | `unknown_after_post` |
| HTTP canceled | см. таблицу границ | `canceled` |
| HTTP succeeded | — | `succeeded` (+ `fiscal_status`) |

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC. Follow-up: RPC + `FOR UPDATE SKIP LOCKED`.

### 3. Idempotence-Key (rev3–rev5)

Ключ: `reconcile:{yk_payment_id}:{attempt}`, где **`attempt` = значение `reconcile_attempts` после инкремента и до HTTP** (уже в БД). При `unknown_after_post` на следующем тике `attempt` **не** увеличивается — ключ тот же.

Чек-лист до кода:

- [ ] Сверить TTL в [доке ЮKassa](https://yookassa.ru/developers/using-api/interaction-format#idempotence) (часто 24 ч — **проверить**). От TTL зависит, **сколько 10-мин тиков** допустима ветка «тот же ключ».
- [ ] Прокинуть ключ в `create_receipt` / `_post` **только** для пути reconcile (webhook / ручной CLI — uuid4 или отдельное решение в том же PR).

### 4. Тесты на ключ / исход / алерт

9. Имитировать **таймаут на ответе** POST → `reconcile_last_outcome=unknown_after_post`, **без** +1; повтор (в т.ч. «следующий тик») с тем же `attempt` / ключом.  
10. После `canceled` receipt → +1 / новый ключ; `outcome=canceled`.  
11. `reconcile_attempts >= 3` → алерт **один** раз (`reconcile_alerted_at` заполнен); второй тик алерт не шлёт.  
12. Тик при `unknown_after_post` + gate уже видит succeeded → skip, без нового create.

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция (**все** 4 колонки, в т.ч. outcome + alerted) на preview/копии + `list_succeeded_payments`.
2. Job/service в **dry-run**; lease; границы rev4 + ветвление по `reconcile_last_outcome` (rev5).
3. CLI `fiscal-reconcile-tick` + systemd timer/service.
4. Тесты 1–12.
5. Документ в `docs/yookassa-setup.md`.

## Тесты (минимум)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip `succeeded_payment_receipt_exists` (в т.ч. «после таймаута чек уже есть»)  
3. `reg=pending` → skip (**без** роста `reconcile_attempts`)  
4. `reg` пустой → skip, create **не** вызывается (**без** роста attempts)  
5. Два тика подряд → 1 чек (lease + backoff + idem key)  
6. Вне окна 48 ч / младше grace → skip  
7. Ошибка **`list_receipts` до POST create** → +1, `outcome=error_before_post`, create нет  
8. После **3** учтённых попыток → алерт **один** раз, create не зовём  
9. Таймаут **на ответе** POST → `unknown_after_post`, тот же ключ на повторе/следующем тике  
10. После canceled receipt → новый `attempt` / новый ключ  
11. Повторный тик после алерта → второй алерт **не** уходит  
12. `unknown_after_post` + gate succeeded → skip без create  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»** (или эквивалент). До неё — только этот дизайн + Tracker.
