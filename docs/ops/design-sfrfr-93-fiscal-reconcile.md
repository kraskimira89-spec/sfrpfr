# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev8: HTTP 500≈unknown, тело при повторе, gate на unknown — замечание Стратега к #243).
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

## Решения реализации (rev2–rev8)

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
       'canceled', 'succeeded', 'pending',
       'skip_reg', 'skip_pending'   -- разные причины skip для логов
     ))
```

- **`reconcile_post_at`:** пишется **один раз** вместе с переходом в `post_started` (перед HTTP), значением `now()` БД. Lease **не** обновляет это поле. Сброс/`NULL` — только при новом create-пути (+1 / новый ключ после TTL expiry или после `canceled`). Без этой колонки тест 13 нельзя посчитать честно: `last_reconcile_at` «плывёт» на каждом lease.
- **`reconcile_post_payload`:** JSON тела create при первом POST; на повторе с тем же ключом слать его без изменений (rev8).
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
| сбой `list_receipts` / gate на ветке `unknown_after_post` / `post_started` (TTL жив) | **не** трогать; повторить на следующем тике | прежний |
| **перед** успешным стартом POST `create_receipt` | **+1**, значение → в ключ | `reconcile:{yk_id}:{attempt}` (≤64 символа) |
| таймаут / обрыв / **HTTP 500** после отправки POST (неизвестно, создала ли ЮKassa чек) | **не** инкрементировать; outcome=`unknown_after_post` | **повторить тот же ключ** в пределах TTL |
| HTTP-ответ: receipt `canceled`, нужен новый чек | **+1** → новый ключ | новый attempt |
| HTTP-ответ: succeeded / pending | стоп; при succeeded можно выставить `fiscal_status=registered` | — |
| TTL ключа истёк, нужен повтор create | **+1** (старый ключ нельзя) | новый attempt |

Одной строкой канон: **таймаут, обрыв или HTTP 500 после POST `create_receipt` → не +1, outcome=`unknown_after_post`, повторить прежний ключ в пределах TTL.** Иначе новый ключ = второй чек (дубль как 777+778).  
Дока ЮKassa: HTTP 500 за 30 с **не** значит неуспех — сначала выяснить результат (через `list_receipts` / повтор с тем же ключом), потом решать.

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

1. Всегда сначала gate / `list_receipts`. Если есть succeeded/pending `type=payment` → skip, `succeeded`/`pending`, **не** create.
2. Если `list_receipts` **упал** на этой ветке и TTL жив → **не** +1, outcome оставить `unknown_after_post`/`post_started`, выйти до следующего тика (не жечь лимит attempts без create).
3. Если TTL **жив** → **не** +1; POST с тем же `attempt` / тем же ключом / **тем же телом** (`reconcile_post_at` не трогать).
4. Если TTL **истёк** и чека нет → **+1**, новый ключ, перезаписать `reconcile_post_at` при следующем `post_started`.
5. Если `reconcile_post_at IS NULL` при `unknown_after_post`/`post_started` → считать как истёкший TTL **и** лог **WARNING** + метрика `fiscal_reconcile_post_at_missing` (аномалия).

Перед POST при `unknown_after_post`/`post_started` gate обязателен (тест 2/12).

**Тело запроса при повторе ключа (rev8):** дока: тот же ключ + те же данные = повтор; другой ключ = новый запрос. Поведение при том же ключе и **других** данных не описано → **не менять** тело на повторе. Канон v1: при первом POST сохранить снимок параметров create (amount, description, email, phone) в колонке `reconcile_post_payload jsonb null` (6-я additive в той же миграции) **или** собирать тело только из полей платежа ЮKassa (`fetch_payment`), а не из меняющейся карточки клиента. Предпочтение: **снимок jsonb** — проще тест. На повторе с тем же ключом слать **байт-в-байт** тот же JSON (после нормализации).

**Длина Idempotence-Key (rev8):** ≤ **64** символа (дока). Формат `reconcile:{uuid}:{n}` обычно ≤ 10+36+1+цифры. Перед POST: `assert len(key) <= 64`, иначе ERROR и skip (не слать).

**Алерт один раз, атомарно (rev6):** при `reconcile_attempts >= 3` **или** «48 ч без succeeded receipt» — **лучше потерять один алерт с логом, чем спамить**.

Порядок v1 (канон):

```text
1. UPDATE payments
   SET reconcile_alerted_at = now()
   WHERE id = $id AND reconcile_alerted_at IS NULL
   RETURNING *;
2. Если 0 rows → уже алертили, стоп.
3. Если строка вернулась → отправить алерт (Tracker / лог+метрика).
4. Если отправка упала → лог ERROR + метрика `fiscal_reconcile_alert_send_failed`.
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
| таймаут / HTTP **500** после POST | **не** трогать attempts/`reconcile_post_at` | `unknown_after_post` |
| сбой gate на ветке unknown (TTL жив) | **не** трогать | оставить unknown/post_started |
| HTTP canceled | см. таблицу границ | `canceled` |
| HTTP succeeded | — | `succeeded` (+ `fiscal_status`) |

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC. Follow-up: RPC + `FOR UPDATE SKIP LOCKED`.

### 3. Idempotence-Key (rev3–rev8)

Ключ: `reconcile:{yk_payment_id}:{attempt}`, где **`attempt` = значение `reconcile_attempts` после инкремента и до HTTP**. При `unknown_after_post` / `post_started` и **живом** TTL на следующем тике `attempt` **не** растёт — ключ **и тело** те же. После истечения TTL — +1 и новый ключ (если gate пуст).

Чек-лист до кода:

- [x] TTL ЮKassa = **24 ч** после первого запроса ([дока](https://yookassa.ru/developers/using-api/interaction-format), 2026-10-23).
- [x] Запас **15 мин**; якорь = `reconcile_post_at`, не `last_reconcile_at`.
- [x] HTTP 500 / таймаут после POST → `unknown_after_post` (дока: 500 ≠ неуспех).
- [x] Длина ключа ≤ 64; тело повтора = снимок первой отправки.
- [ ] Прокинуть ключ (+ snapshot body) в `create_receipt` / `_post` **только** для пути reconcile.

### 4. Тесты на ключ / исход / алерт

9. Таймаут **или HTTP 500** на ответе POST → `unknown_after_post`, без +1; повтор с тем же ключом **и тем же телом**.  
10. После `canceled` → +1 / новый ключ.  
11. `attempts >= 3` → алерт один раз (RETURNING); второй тик не шлёт.  
12. `unknown_after_post` + gate succeeded → skip без create.  
13. TTL истёк + list пуст → +1, новый ключ.  
14. Kill после `post_started` → следующий тик как unknown, тот же ключ при живом TTL.  
15. Lease не двигает `reconcile_post_at`.  
16. CLI reset: `alerted_at` + `attempts` вместе.  
17. На ветке unknown сбой `list_receipts` → **без** +1, outcome не менять.  
18. `reconcile_post_at IS NULL` при unknown → WARNING/метрика + путь как TTL истёк.  
19. Ключ длиннее 64 → skip, create не слать.

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция (**6** колонок: attempts, last_reconcile_at, post_at, outcome, alerted_at, **post_payload jsonb** + CHECK) на preview/копии + `list_succeeded_payments` + stale-48h list.
2. Job/service в **dry-run**; lease; границы rev4–rev8.
3. CLI `fiscal-reconcile-tick` + reset-алерта + systemd timer/service.
4. Тесты 1–19.
5. Документ в `docs/yookassa-setup.md`.

## Тесты (минимум)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip `succeeded_payment_receipt_exists` (в т.ч. «после таймаута чек уже есть»)  
3. `reg=pending` → skip (**без** роста `reconcile_attempts`)  
4. `reg` пустой → skip, create **не** вызывается (**без** роста attempts)  
5. Два тика подряд → 1 чек (lease + backoff + idem key)  
6. Вне окна 48 ч / младше grace → skip из create-выборки; **алерт 48ч** — отдельным запросом  
7. Ошибка **`list_receipts` до POST create** → +1, `outcome=error_before_post`, create нет  
8. После **3** учтённых попыток → алерт **один** раз (сначала UPDATE … RETURNING), create не зовём  
9. Таймаут **на ответе** POST → `unknown_after_post`, тот же ключ на повторе/следующем тике  
10. После canceled receipt → новый `attempt` / новый ключ  
11. Повторный тик после алерта → второй алерт **не** уходит  
12. `unknown_after_post` + gate succeeded → skip без create  
13. TTL истёк (`reconcile_post_at`) + `unknown_after_post` + list пуст → +1 и новый ключ  
14. После `post_started` (имитация kill) → следующий тик без +1 / тот же ключ (TTL жив)  
15. После lease `reconcile_post_at` неизменен  
16. CLI reset: `alerted_at` + `attempts` сбрасываются вместе  
17. Сбой gate на unknown → без +1  
18. `reconcile_post_at IS NULL` → WARNING + путь TTL-истёк  
19. Ключ > 64 символов → skip  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»** (или эквивалент). До неё — только этот дизайн + Tracker.
