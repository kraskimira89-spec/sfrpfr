# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev9: gate+TTL-истёк, 4xx/`rejected`, jsonb≠байты — замечание Стратега к #244).
Источник: разбор Стратега по `main` + пути в репо + [дока ЮKassa](https://yookassa.ru/developers/using-api/interaction-format).
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

## Решения реализации (rev2–rev9)

### 1. Хранение попыток / исхода / алерта / момента POST — миграция Supabase

Алгоритм требует «запись попытки», исход **между тиками** и **неподвижный** момент POST для TTL; места в схеме сейчас **нет**.

**Канон (вариант 1 Стратега — выбран):** additive-колонки на `public.payments`:

```text
supabase/migrations/<timestamp>_payments_fiscal_reconcile_attempts.sql
  + reconcile_attempts       int  not null default 0
  + last_reconcile_at        timestamptz null   -- lease; перезаписывается каждым тиком
  + reconcile_post_at        timestamptz null   -- момент отправки POST create; НЕ трогает lease
  + reconcile_post_payload   jsonb null         -- снимок тела первой отправки (повтор ключа)
  + reconcile_last_outcome   text null
  + reconcile_alerted_at     timestamptz null
  + CHECK (reconcile_last_outcome IS NULL OR reconcile_last_outcome IN (
       'error_before_post', 'post_started', 'unknown_after_post',
       'canceled', 'succeeded', 'pending', 'rejected',
       'skip_reg', 'skip_pending'
     ))
```

- **`reconcile_post_at`:** пишется **одним UPDATE** вместе с `+1`, `post_started` и `reconcile_post_payload` **перед** HTTP (`now()` БД). Lease **не** трогает. Сброс — только на новом create-пути (TTL expiry / после `canceled` / после `rejected` при новом create).
- **`reconcile_post_payload`:** снимок тела; на повторе с тем же ключом — **смысловое** совпадение (см. rev9 jsonb), не побайтовое. После `succeeded` → **очистить** payload (`NULL`), чтобы email/телефон не лежали в `payments` вечно. На пути «TTL истёк» → **пересобрать** снимок заново, не брать старый.
- RLS/grants: те же роли, что уже пишут `payments`; grant на anon не расширять.
- `DEFAULT 0` / `NULL` — существующие строки ок; миграция **только ADD COLUMN** + CHECK.
- Перед apply на прод: копия / Supabase preview (коммит 1 — самый рискованный).
- Вариант 2 — **отклонён** (см. rev5).
- Отдельная таблица истории — отложить.

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
| ошибка **до** POST на **обычном** пути (упал `fetch_payment` / `list_receipts`, outcome ≠ unknown/post_started) | **+1** | не использовался |
| сбой `list_receipts` / gate на ветке unknown/`post_started` (**TTL жив или истёк**) | **не** трогать; **не** create; следующий тик | прежний (если жив) / не слать новый |
| **перед** POST `create_receipt` (один UPDATE: +1, `post_started`, `post_at`, payload) | **+1** → в ключ | `reconcile:{yk_id}:{attempt}` (≤64) |
| таймаут / обрыв / **HTTP 500 / 502 / 503 / 504 / 429** после POST | **не** +1; `unknown_after_post` | тот же ключ в пределах TTL |
| HTTP **4xx** (кроме 429): чек точно не создан | attempt уже +1 до POST; outcome=`rejected`; **не** повторять тем же ключом | новый attempt при следующей попытке |
| HTTP: receipt `canceled`, нужен новый чек | +1 → новый ключ | новый |
| HTTP: succeeded / pending | стоп; succeeded → `fiscal_status=registered`, **payload=NULL** | — |
| TTL истёк + gate OK + list пуст | +1, **новый** payload, новый ключ | новый |

Канон unknown: **таймаут / обрыв / 5xx (500–504) / 429 после POST → не +1, `unknown_after_post`, тот же ключ пока TTL жив.**  
Канон 4xx: **определённый отказ → `rejected`, попытка израсходована, тот же ключ не слать.**  
Дока: HTTP 500 ≠ неуспех — сначала результат через list / повтор ключа.

**Между тиками (rev5 + rev6):** состояние процесса не живёт 10 минут → ветку выбирает `reconcile_last_outcome`:

| `reconcile_last_outcome` | На следующем тике |
|--------------------------|-------------------|
| `unknown_after_post` | см. ветку TTL ниже |
| `post_started` | **как `unknown_after_post`** (kill/OOM между записью и ответом: POST мог уйти) |
| `error_before_post` | обычный путь (можно новый +1 при следующей ошибке/create по таблице границ) |
| `canceled` | нужен новый create → +1 и новый ключ (если attempts < 3) |
| `succeeded` / `pending` | skip (gate / fiscal_status) |
| `null` | первый заход; обычный путь |

**Ветка `unknown_after_post` / `post_started` и TTL (rev6–rev7):**

**Канон TTL ЮKassa (сверено 2026-10-23):** идемпотентность **24 часа** после первого запроса с данным ключом  
([дока](https://yookassa.ru/developers/using-api/interaction-format): «ЮKassa обеспечивает идемпотентность в течение 24 часов после первого запроса, потом повторный запрос будет обработан как новый»).

Константы v1:

```text
YOOKASSA_IDEMPOTENCE_TTL = 24h
RECONCILE_IDEMPOTENCE_MARGIN = 15 min   # не слать «тот же ключ» у края TTL
TTL жив ⇔ (now() - reconcile_post_at) < (24h - 15min)
# тик 10 мин + запас 15 мин ⇒ последний «безопасный» повтор ≥ ~5 мин до истечения ключа;
# тик с отставанием (сбой timer) → ветка «TTL истёк» (gate → +1/новый ключ), не слепой повтор
```

Порядок:

1. Всегда сначала gate / `list_receipts`. Если есть succeeded/pending `type=payment` → skip, `succeeded`/`pending`, payload=NULL, **не** create.
2. Если `list_receipts` **упал** (TTL **жив или истёк**) → **не** +1, **не** create, outcome не менять; следующий тик. Защита от вечного цикла — алерт «48 ч» (не жечь attempts и не рисковать новым ключом, пока неясно, есть ли чек).
3. Если TTL **жив** → **не** +1; POST с тем же `attempt` / ключом / **тем же смысловым телом** из снимка.
4. Если TTL **истёк** и list **успешно** пуст → **+1**, **пересобрать** payload, новый ключ, один UPDATE перед HTTP.
5. Если `reconcile_post_at IS NULL` при unknown/`post_started` → как TTL истёк **и** WARNING + `fiscal_reconcile_post_at_missing`.

**Тело при повторе (rev8–rev9):** тот же ключ ⇒ те же **данные**. `jsonb` в Postgres **не** хранит исходный текст (порядок ключей/пробелы теряются) → формулировка «байт-в-байт» **запрещена**. Канон: сериализация снимка с `sort_keys=True` и фиксированными разделителями (`separators=(',', ':')`); `amount.value` хранить **строкой** (`"2.00"`), не float. Тест 9 сравнивает **разобранные** dict/JSON, не сырые строки.

**Длина ключа:** ≤ **64**. Иначе ERROR + skip.

**Алерт один раз, атомарно (rev6 + rev9):** при (`reconcile_attempts >= 3` **и** outcome **не** в `{unknown_after_post, post_started}` при живом TTL) **или** «48 ч без succeeded receipt» — лучше потерять алерт с логом, чем спамить.

Пока исход unknown и TTL жив — алерт по attempts **не** слать (ещё может подтвердиться чек). Если attempts≥3 и unknown, но TTL уже истёк / gate пуст и create запрещён лимитом — алерт с текстом «возможен неподтверждённый чек; проверить list_receipts вручную».

Порядок v1:

```text
1. UPDATE … SET reconcile_alerted_at = now() WHERE … IS NULL RETURNING *;
2. 0 rows → стоп.
3. Строка есть → send; fail → ERROR + fiscal_reconcile_alert_send_failed.
```

**Сброс алерта (rev7, CLI):** одной командой сбрасывать **оба**:

```text
reconcile_alerted_at = NULL
reconcile_attempts   = 0
-- опционально: reconcile_last_outcome / reconcile_post_at по решению оператора
```

Если сбросить только `reconcile_alerted_at` при `attempts >= 3`, следующий тик снова алертит. Не делать partial reset по умолчанию.

**Выборка для алерта «48 ч» (rev6):** отдельный запрос, **не** тот же, что кандидаты reconcile в окне 48 ч:

```text
paid_at < now() - interval '48 hours'
AND fiscal_status IS DISTINCT FROM 'registered'   -- или через or_ NULL
AND reconcile_alerted_at IS NULL
AND status = 'succeeded'
AND provider_payment_id IS NOT NULL
```

Иначе платёж на границе окна выпадет из reconcile-выборки и алерт не уйдёт никогда. Кандидаты create остаются: `paid_at` в `[now-48h, now-grace]`.

| Исход после lease | `reconcile_attempts` | `reconcile_last_outcome` |
|-------------------|----------------------|--------------------------|
| skip: `reg` пустой / не canceled (не pending) | **не** трогать | `skip_reg` |
| skip: `reg=pending` | **не** трогать | `skip_pending` |
| skip: gate | **не** трогать | `succeeded` / `pending` |
| dry-run | **не** трогать | не менять / `null` |
| ошибка **до** POST create | **+1** | `error_before_post` |
| старт POST create | **+1** до HTTP; **`reconcile_post_at = now()`** | `post_started` → по ответу |
| таймаут / 500–504 / 429 после POST | **не** трогать attempts/`post_at`/payload | `unknown_after_post` |
| HTTP 4xx (не 429) | attempt уже +1 | `rejected` |
| сбой gate (TTL жив **или** истёк) | **не** трогать; **не** create | оставить unknown/post_started |
| HTTP canceled | см. границы | `canceled` |
| HTTP succeeded | payload → NULL | `succeeded` (+ `fiscal_status`) |

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC. Follow-up: RPC + `FOR UPDATE SKIP LOCKED`.

### 3. Idempotence-Key (rev3–rev9)

Ключ: `reconcile:{yk_payment_id}:{attempt}` после инкремента и до HTTP. Unknown + живой TTL → тот же ключ и **то же смысловое тело**. TTL истёк + list пуст → +1, новый ключ, новый payload.

Чек-лист:

- [x] TTL 24 ч; запас 15 мин; якорь `reconcile_post_at`.
- [x] 500–504 / 429 / таймаут → unknown; 4xx (не 429) → `rejected`.
- [x] Ключ ≤ 64; тело = jsonb-снимок с `sort_keys` (не байт-в-байт).
- [x] Сбой gate при любом TTL → без create / без +1.
- [ ] Прокинуть ключ + payload в путь reconcile only.

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция (6 колонок + CHECK с `rejected`) на preview + `list_succeeded_payments` + stale-48h.
2. Job dry-run; границы rev4–rev9.
3. CLI tick + reset-алерта + systemd.
4. Тесты **1–21** (единственный список ниже).
5. `docs/yookassa-setup.md`.

## Тесты (канон, один список)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip gate (в т.ч. после таймаута)  
3. `reg=pending` → skip, без роста attempts (`skip_pending`)  
4. `reg` пустой → skip, без create / без роста attempts (`skip_reg`)  
5. Два тика подряд → 1 чек (lease + idem)  
6. Вне create-окна → skip; алерт 48ч — отдельным SELECT  
7. Ошибка `list_receipts` на **обычном** пути (не unknown) → +1, `error_before_post`  
8. `attempts >= 3` и не unknown-с-живым-TTL → алерт один раз (RETURNING)  
9. Таймаут / **500** / **502** на ответе → `unknown_after_post`; повтор: тот же ключ; тела сравнить как dict (`sort_keys`), не как строки  
10. После `canceled` → +1 / новый ключ / новый payload  
11. Повторный тик после алерта → второй алерт не уходит  
12. `unknown_after_post` + gate succeeded → skip, payload NULL  
13. TTL истёк + list **успешно** пуст → +1, новый ключ, **новый** payload  
14. Kill после `post_started` → следующий тик без +1 / тот же ключ (TTL жив)  
15. Lease не двигает `reconcile_post_at`  
16. CLI reset: `alerted_at` + `attempts` вместе  
17. Сбой gate на unknown при **живом** TTL → без +1 / без create  
18. `reconcile_post_at IS NULL` → WARNING + путь TTL-истёк  
19. Ключ > 64 → skip  
20. Сбой gate на unknown при **истёкшем** TTL → без +1 / без create (не новый ключ)  
21. HTTP 400 → `rejected`; следующий create — новый ключ (не повтор)  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»**. До неё — только этот дизайн + Tracker.
