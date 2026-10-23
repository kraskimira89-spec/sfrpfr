# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23** (rev10: ensure API, cutover алертов, lease CLI — блокирующие 3–5 к #244).
Источник: разбор Стратега + [дока ЮKassa](https://yookassa.ru/developers/using-api/interaction-format).
Код **не** стартовать без команды владельца («делаем SFRFR-93»).

## Цель

Тонкая обёртка над уже существующими `ensure_payment_receipt`, `payment_receipt_retry_gate`, `should_auto_retry_fiscal_receipt` — не новая логика фискализации.

## Три ловушки (канон)

1. **Пустой `receipt_registration`.** `ensure` пропускает только `succeeded`/`pending`; при пустом идёт к `GET /receipts` и может создать чек. Job **обязан** до вызова ensure проверить `should_auto_retry_fiscal_receipt(reg)` (истина только для `canceled`/`cancelled`) — иначе риск дубля как FD 777+778.
2. **`canceled` ≠ «чека нет».** После фискализации поле может остаться `canceled` (FD 770/771); решающий фильтр — gate по списку чеков внутри ensure.
3. **`Idempotence-Key` сейчас `uuid4` в `_post`.** Параллельные тики = два чека. Для reconcile нужен детерминированный ключ (`reconcile:{payment_id}:{attempt}`) + блокировка на платёж.

## Алгоритм (согласован)

Для кандидата: предфильтр БД → окно 48 ч / grace ≥2 мин → lease → `fetch_payment` → `should_auto_retry_fiscal_receipt` → иначе skip → `ensure_payment_receipt(..., idempotence_key=, body_snapshot=)` → запись исхода → алерт по правилам ниже.

Флаги: `FISCAL_RECONCILE_ENABLED=0` (default); `FISCAL_RECONCILE_DRY_RUN=1` (default при первом включении). Период: **каждые 10 мин**. Отдельный systemd timer. Слово «backoff» = пауза между тиками (**10 мин**) + `lease_secs=120`; отдельной экспоненты нет.

## Пути в коде (ответы на допущения)

| Вопрос | Ответ |
|--------|--------|
| Где платежи | Таблица `public.payments` (миграции `supabase/migrations/20260722122128_b2c_schema_rls.sql`, `…_payments_one_active_per_order.sql`). Поля: `status`, `provider_payment_id`, `paid_at`, `created_at`, `fiscal_status`, `order_id`. |
| Предфильтр `fiscal_status` | Колонка **есть и пишется**: webhook ставит `fiscal_status="registered"`, если в событии `fiscal` truthy (`payments.py` → `apply_provider_payment`). Кандидаты reconcile: `status=succeeded` и `fiscal_status IS DISTINCT FROM 'registered'` (плюс окно по `paid_at`). Это **дешёвый** отсев; решающий фильтр всё равно YK `reg` + gate. Не полагаться на `fiscal_status` как на «чека точно нет». |
| Как достать за 48 ч | Готового list-by-window **нет**. Нужен метод `list_succeeded_payments(since, until)` в `src/sfrfr/db/case_repository.py`: `status=succeeded` + `paid_at` (fallback `created_at`) + непустой `provider_payment_id` + предфильтр `fiscal_status`. **PostgREST:** `IS DISTINCT FROM 'registered'` для NULL — через `.or_("fiscal_status.is.null,fiscal_status.neq.registered")` (или эквивалент); на реальном клиенте проверить, что строки с `NULL` не теряются. |
| Лимит попыток | **`reconcile_attempts` max = 3**: create разрешён, пока `attempts < 3` **до** инкремента. Инкремент **только** при старте POST create (в т.ч. повтор после `canceled`/`rejected`). Ошибки **до** POST (`fetch`/`list` на обычном пути) → **без** +1 (как сбой gate на unknown). |
| Email/телефон | Как webhook: `_retry_fiscal_receipt` → `clients.email` / `phone`; в payload только на время unknown. |
| CLI retry | `yookassa-retry-receipt` **берёт тот же lease**, что reconcile; при занятом lease — exit non-zero. Runbook: перед ручным массовым retry — `systemctl stop sfrfr-fiscal-reconcile.timer`. |
| Ensure / gate | `src/sfrfr/integrations/payments/__init__.py` — см. § «Сигнатура ensure» (rev10). |
| Cutover алертов | `FISCAL_RECONCILE_ALERT_SINCE` (timestamptz) — нижняя граница `paid_at` для алертов 48ч; иначе шторм по всей истории. |
| Таймер | `sfrfr-fiscal-reconcile.timer` + `fiscal-reconcile-tick`; не смешивать с finance-due. |
| Тесты | `tests/unit/test_yookassa.py` + новые reconcile. |

## Решения реализации (rev2–rev10)

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
  + CONSTRAINT payments_reconcile_last_outcome_chk CHECK (
       reconcile_last_outcome IS NULL OR reconcile_last_outcome IN (
         'error_before_post', 'post_started', 'unknown_after_post',
         'canceled', 'succeeded', 'pending', 'rejected',
         'skip_reg', 'skip_pending'
       )
     )
```

Имя `payments_reconcile_last_outcome_chk` — чтобы расширять список отдельной миграцией без поиска автогенерации.

- **`reconcile_post_at`:** пишется **одним UPDATE** вместе с `+1`, `post_started` и `reconcile_post_payload` **перед** HTTP (`now()` БД). Lease **не** трогает. Сброс — только на новом create-пути (TTL expiry / после `canceled` / после `rejected` при новом create).
- **`reconcile_post_payload`:** снимок тела; на повторе с тем же ключом — **смысловое** совпадение (см. rev9 jsonb), не побайтовое. После `succeeded` → **очистить** payload (`NULL`), чтобы email/телефон не лежали в `payments` вечно. На пути «TTL истёк» → **пересобрать** снимок заново, не брать старый.
- RLS/grants: те же роли, что уже пишут `payments`; grant на anon не расширять.
- `DEFAULT 0` / `NULL` — существующие строки ок; миграция **только ADD COLUMN** + CHECK.
- Перед apply на прод: копия / Supabase preview (коммит 1 — самый рискованный).
- Вариант 2 — **отклонён** (см. rev5).
- Отдельная таблица истории — отложить.

### 2. Lease и счётчик (rev3 — канон)

Через PostgREST/`supabase-py` **нет** прямого `FOR UPDATE SKIP LOCKED` / advisory lock без RPC.

**Время:** lease, TTL и cutover — только **`now()` базы** (SQL/RPC), не `datetime.now()` Python. Флаг «TTL жив» считать в SQL, например:

```sql
(reconcile_post_at IS NOT NULL
 AND now() - reconcile_post_at < interval '24 hours' - interval '15 minutes')
```

Чек-лист ревью: запрет Python-времени для TTL/lease.

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
| ошибка **до** POST на обычном пути (`fetch`/`list`) | **не** +1; outcome=`error_before_post`; следующий тик | не использовался |
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

**Выборка для алерта «48 ч» (rev6 + rev10 cutover):** отдельный запрос. Одинаковое время с кандидатами: `coalesce(paid_at, created_at)`.

```text
coalesce(paid_at, created_at) < now() - interval '48 hours'
AND coalesce(paid_at, created_at) >= FISCAL_RECONCILE_ALERT_SINCE   -- обязателен при ENABLED=1
AND fiscal_status IS DISTINCT FROM 'registered'   -- or_ NULL в PostgREST
AND reconcile_alerted_at IS NULL
AND status = 'succeeded'
AND provider_payment_id IS NOT NULL
```

Без `ALERT_SINCE` включать ENABLED **запрещено** (иначе шторм по всей истории, где webhook не ставил `registered`). Альтернатива cutover: разовый SQL `UPDATE payments SET reconcile_alerted_at = now() WHERE coalesce(paid_at,created_at) < :since AND reconcile_alerted_at IS NULL` перед первым ENABLED=1.

**Dry-run (rev10):** пишет только `last_reconcile_at` (lease); **не** трогает attempts / post_at / payload / outcome; **не** шлёт алерты; **не** вызывает create. Лог: «создал бы для payment_id=…».

| Исход после lease | `reconcile_attempts` | `reconcile_last_outcome` |
|-------------------|----------------------|--------------------------|
| skip: `reg` пустой / не canceled (не pending) | **не** трогать | `skip_reg` |
| skip: `reg=pending` | **не** трогать | `skip_pending` |
| skip: gate | **не** трогать | `succeeded` / `pending` |
| dry-run | только `last_reconcile_at` | не менять |
| ошибка **до** POST create | **не** +1 | `error_before_post` |
| старт POST create | **+1** + post_at + payload одним UPDATE | `post_started` → по ответу |
| таймаут / 500–504 / 429 после POST | **не** трогать attempts/`post_at`/payload | `unknown_after_post` |
| HTTP 4xx (не 429) | attempt уже +1 | `rejected` |
| сбой gate (TTL жив **или** истёк) | **не** трогать; **не** create | оставить unknown/post_started |
| HTTP canceled | см. границы | `canceled` |
| HTTP succeeded | payload → NULL | `succeeded` (+ `fiscal_status`) |

**Не** закладывать `pg_advisory_lock` / `SKIP LOCKED` в v1 без RPC. Follow-up: RPC + `FOR UPDATE SKIP LOCKED`.

### 3. Сигнатура ensure / `_post` (rev10 — блокер)

Логику фискализации **не** дублировать; расширить существующие методы:

```text
YooKassaClient._post(path, payload, *, idempotence_key: str | None = None)
  # если key задан → заголовок Idempotence-Key = key (после len<=64)
  # иначе → uuid4 (как сейчас: webhook / старый CLI без snapshot)

YooKassaClient.create_receipt(..., *, idempotence_key: str | None = None)
  # прокидывает key в _post; body = собранный payload

YooKassaClient.ensure_payment_receipt(
    ...,
    *,
    idempotence_key: str | None = None,
    body_snapshot: dict | None = None,
)
  # если body_snapshot задан → POST этим телом (после sort_keys-сериализации),
  #   не пересобирать customer/amount из карточки;
  # иначе → текущая сборка тела (webhook-путь);
  # idempotence_key только на reconcile / CLI-с-lease
```

Webhook `_retry_fiscal_receipt` и обычный CLI без snapshot → `uuid4`, без lease (кроме обновлённого CLI — см. ниже).

### 4. Гонка webhook / CLI / reconcile (rev10 — блокер)

| Путь | Lease | Idempotence-Key |
|------|-------|-----------------|
| reconcile tick | да | `reconcile:…` |
| `yookassa-retry-receipt` | **да** (тот же UPDATE lease) | предпочтительно `reconcile:…` если attempts уже есть, иначе uuid4 + WARNING |
| webhook `_retry_fiscal_receipt` | нет (короткий request) | uuid4 |

Минимум ops: в `docs/yookassa-setup.md` — «ручной retry при остановленном `sfrfr-fiscal-reconcile.timer`».  
Лучше (канон кода): CLI всегда lease; если 0 rows — «занято, повторите позже».

### 5. Idempotence-Key (rev3–rev10)

Ключ: `reconcile:{yk_payment_id}:{attempt}` после инкремента и до HTTP. Unknown + живой TTL → тот же ключ и смысловое тело. TTL истёк + list пуст → +1, новый ключ, новый payload.

Чек-лист:

- [x] TTL 24 ч; запас 15 мин; якорь `reconcile_post_at`; TTL-флаг в **SQL**.
- [x] 500–504 / 429 / таймаут → unknown; 4xx (не 429) → `rejected`.
- [x] Ключ ≤ 64; тело = jsonb + `sort_keys`.
- [x] Сбой gate при любом TTL → без create / без +1.
- [x] Сигнатура ensure/create/`_post` с `idempotence_key` + `body_snapshot` (только reconcile/CLI).
- [x] `FISCAL_RECONCILE_ALERT_SINCE` / backfill; dry-run без алертов.
- [x] CLI берёт lease; runbook stop timer.
- [ ] Реализовать в коде (после «делаем SFRFR-93»).

## Порядок коммитов (когда скажут «делаем SFRFR-93»)

1. Миграция (6 колонок + **именованный** CHECK) на preview + `list_succeeded_payments` + stale-48h с `ALERT_SINCE`.
2. Расширение `_post` / `create_receipt` / `ensure_payment_receipt` + тесты сигнатуры.
3. Job dry-run; границы rev4–rev10; lease CLI.
4. CLI tick + reset-алерта + systemd + runbook.
5. Тесты **1–27**; `docs/yookassa-setup.md`.

## Тесты (канон, один список)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip gate  
3. `reg=pending` → skip, без роста attempts (`skip_pending`)  
4. `reg` пустой → skip, без create / без роста (`skip_reg`)  
5. Два тика подряд → 1 чек (lease; пауза = период тика)  
6. Вне create-окна → skip; алерт 48ч — отдельный SELECT с cutover  
7. Ошибка `list_receipts` на обычном пути → **без** +1, `error_before_post`  
8. `attempts >= 3` и не unknown-с-живым-TTL → алерт один раз  
9. Таймаут / 500 / 502 → unknown; повтор: тот же ключ; тела как dict  
10. После `canceled` → +1 / новый ключ / новый payload  
11. Повторный тик после алерта → второй алерт не уходит  
12. unknown + gate succeeded → skip, payload NULL  
13. TTL истёк + list пуст → +1, новый ключ, новый payload  
14. Kill после `post_started` → следующий тик без +1 / тот же ключ  
15. Lease не двигает `reconcile_post_at`  
16. CLI reset: `alerted_at` + `attempts` вместе (+ payload NULL)  
17. Сбой gate, TTL жив → без +1 / без create  
18. `reconcile_post_at IS NULL` → WARNING + путь TTL-истёк  
19. Ключ > 64 → skip  
20. Сбой gate, TTL истёк → без +1 / без create  
21. HTTP 400 → `rejected`; следующий create — новый ключ  
22. Сериализация снимка стабильна (`sort_keys`); повтор ≡ dict  
23. Снимок очищается после `succeeded`  
24. Первый запуск с `ALERT_SINCE` / backfill **не** алертит историю  
25. `fiscal_status IS NULL` попадает в предфильтр (PostgREST)  
26. Dry-run: только `last_reconcile_at`; без attempts/post_at/outcome/алертов/create  
27. Три сетевых сбоя `fetch_payment` подряд **не** доводят attempts до 3  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»**. До неё — только этот дизайн + Tracker.  
Блокеры Стратега 1–5 закрыты в rev9–rev10 (текст); реализация — после команды.
