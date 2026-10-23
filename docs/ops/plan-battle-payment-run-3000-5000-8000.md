# План боевого прогона платежей 3000 / 5000 / 8000

Дата плана: **2026-10-23** (обновление: smoke #226 PASS формально, **живая гонка pending не проверена**; HTTP-путь pending закрыт тестом; боевые 3/5/8k возвращены).
Не смешивать с приёмкой механики на малых суммах (1/3/5/8 ₽) — кроме **шага 0** (smoke 1₽ для снятия блокера дублей).

## Предусловия (до первой полной суммы)

| Проверка | Требование |
|----------|------------|
| Shop | **1421177** (`YOOKASSA_SHOP_ID`) |
| Тест-флаг | `PAYMENT_TEST_AMOUNT_ENABLED=0` на **всех** шагах (smoke и боевые). **Не** включать `=1` |
| Касса | Evotor **online**, смена открыта |
| Дубли FD | Smoke #220/#226 без дубля; live closed-shift (`326d8c70…`) тоже 1× payment, но `reg=succeeded` сразу. Статус: **`SMOKE_OK_RACE_UNVERIFIED` + `PENDING_PATH_HTTP_VERIFIED`** (не полный `BLOCKER_CLEARED`) |
| Владелец денег | явное «да, платим N» на **каждый** шаг; иначе стоп |
| Reconcile | руками **не** делать без отдельного разрешения |

## Владелец денег

| Поле | Значение |
|------|----------|
| Решение оставить / вернуть | **Вернули** боевые 3000+5000+8000 (2026-10-23, команда владельца). Smoke 1₽ **не** возвращали |
| Кто подтверждает оплату | владелец («да, платим N») |
| Кто инициирует возврат в YK | владелец («сделай возврат…» / «да, возвращаем») |

## Порядок прогона

0. **SMOKE — 1 ₽** (снятие блокера дублей, не боевой тариф)
   - #220: ✅ PASS `326d7173…`, FD **774** → `BLOCKER_CLEARED` (затем FAIL на SUPPORT 8000).
   - #226: ✅ PASS `326d88ae-000f-5001-9000-1b6e2eb6d4fc`, 1× `type=payment` → снова **`BLOCKER_CLEARED`**.
   История #226: `docs/history/2026-10-23-smoke-dedup-226-1rub.md`.
1. **DIAG — 3000 ₽** — ✅ **PASS** 2026-10-23
   Payment `326d7bdd-000f-5001-8000-1d4633098c55`, shop **1421177**, **3000.00**, FD **775**, webhook 200 → order paid без reconcile, 1 payment, 1× `type=payment`, ENABLED=0.
   Дело **ПС-786706** (`is_test`) → `diagnostic_paid`.
   История: `docs/history/2026-10-23-battle-diag-3000.md` (**не** путать с `payment-3000-acceptance.md`).
2. **DOCS — 5000 ₽** — ✅ **PASS** 2026-10-23
   Payment `326d7d8c-000f-5001-9000-1ed138d35859`, order `fc6c80b4-…906e` paid, shop **1421177**, **5000.00**, FD **776**, webhook 200, 1 payment, 1× `type=payment`, ENABLED=0.
   Тариф **ACCOMP / DOCS** (не «анализ+обращения»). Дело → `service_paid`.
   История: `docs/history/2026-10-23-battle-docs-5000.md`.
3. **SUPPORT — 8000 ₽** — ❌ **FAIL** 2026-10-23 (`FAIL_DUP_RECEIPT`) → деньги **возвращены**; smoke #226 PASS
   Payment (fail) `326d821f-…e2d3`, 2× `type=payment` FD **777**+**778**. История fail: `docs/history/2026-10-23-battle-support-8000.md`.
   Возврат: `326d87d8-…` + 1× `type=refund` (лишний приход в ОФД остаётся — бухгалтер).
   Повторный SUPPORT 8000 — **только** по новому «да, платим 8000» (после `BLOCKER_CLEARED` #226).

Между шагами: зафиксировать FD / сумму / shop; при **втором** `type=payment` succeeded на один `payment_id` — **стоп**, блокер не снят (SFRFR-89), не плодить платежи.

## Известные пробелы Стратега (не блокируют шаг 3 без решения владельца)

| Пробел | Статус |
|--------|--------|
| Pending-ссылки / смена Evotor до оплаты | Известно; на DIAG/DOCS смена была открыта (FD 775/776 succeeded) |
| MAX: у smoke-дела нет `max_user_id` | Известно; клиентский MAX-путь не закрыт этим прогоном |
| Повторный клик «Оформить» / второй счёт | Известно; в боевых шагах оформляли **один** раз; полный UI-регресс — отдельно |

Эти пункты **не** отменяют PASS шагов 1–2 и **не** сами по себе запускают 8000.

## Условия возврата

- ✅ **Сделано 2026-10-23** по команде владельца «сделай возврат 3000 и 5000 и 8000»:
  - DIAG: refund `326d87d2-…198b` succeeded, 1× `type=refund`
  - DOCS: refund `326d87d5-…748c` succeeded, 1× `type=refund`
  - SUPPORT: refund `326d87d8-…93ee` succeeded, 1× `type=refund` при **2×** `type=payment` (FD 777+778)
- История: `docs/history/2026-10-23-battle-refund-3000-5000-8000.md`
- ⚠️ SUPPORT: после возврата денег в учёте остаётся **лишний приход 8000** (2 payment − 1 refund) — коррекция FD с бухгалтером
- Smoke 1₽ и любые новые возвраты — только по отдельной команде

## Чеклист #220 / pre-smoke (владелец)

- [x] Evotor: касса **online** (по факту FD 774 на smoke)
- [x] Evotor: **смена открыта** (по факту succeeded receipt)
- [x] В кабинете ЮKassa виден shop **1421177** (боевой)
- [x] «да, платим 1» → оплата KEEP `326d7173…`
- [x] После деплоя #220: `GET /receipts?payment_id=` → ровно один succeeded `type=payment` (FD **774**)
- [x] Не запускать боевые 3/5/8k до `BLOCKER_CLEARED` (снято; дальше — только отдельные «да, платим N»)

После `BLOCKER_CLEARED` — отдельно «да, платим 3000» / «5000» / «8000».

## Критерии шага (каждый боевой 3/5/8k)

- [x] Charge API = полная сумма (3000 / 5000 / 8000), shop 1421177 — шаги 1–3 charge ок
- [x] Apache `POST …/yookassa/webhook` **200** → order **paid** без reconcile — шаги 1–3
- [x] Ровно один `payments` на order — шаги 1–3
- [ ] Чек(и): 1× `type=payment` — FD **775** / **776** ок; шаг 3 → **2×** (FD **777**+**778**) ❌
- [x] `PAYMENT_TEST_AMOUNT_ENABLED=0` не меняли на 1

## Стоп-правила

- Нет «да, платим N» → не создавать счёт / не оплачивать.
- Smoke 1₽ без «да, платим 1» → **запрещён**.
- Полные суммы без отдельного «да, платим N» → **запрещены**.
- Провал webhook/paid/чека → не второй счёт без Стратега.
- Дубль чека (`type=payment` ×2 succeeded на один payment) → **жёсткий блокер** боевого прогона до фикса в проде + повторного smoke.
- Не писать «тарифы приняты» до успешного прогона **всех трёх** полных сумм по этому плану.

## Статус для отчёта Стратегу (копипаст)

| Код | Когда писать |
|-----|----------------|
| `BLOCKED_DUP_RECEIPT` | Дубль FD/двух succeeded `type=payment` на один payment; фикс не в проде или не проверен |
| `FIX_IN_FLIGHT` | PR/деплой ensure-gate есть, боевой ещё не возобновляли; ждём smoke |
| `BLOCKER_CLEARED` | Фикс в проде + smoke: один payment_id → один succeeded/pending `type=payment` **и** ветка `pending` проверена (live или HTTP webhook) |
| `SMOKE_OK_RACE_UNVERIFIED` | Smoke без дубля, но webhook пришёл уже при `succeeded`; ensure/skipped в логах нет — гонка не воспроизведена |
| `PENDING_PATH_HTTP_VERIFIED` | HTTP `POST …/yookassa/webhook` с `receipt_registration=pending` не зовёт ensure/create_receipt (юнит) |
| `BATTLE_READY` | `BLOCKER_CLEARED` (или smoke + HTTP pending) + Evotor online + `ENABLED=0` + «да, платим» |
| `BATTLE_DIAG_DOCS_PASS` | Шаги 0–2 PASS; шаг 3 SUPPORT 8000 ждёт «да, платим 8000» |
| `BLOCKED_DUP_RECEIPT` | Дубль FD на SUPPORT 8000 (`326d821f…`, FD **777**+**778**); боевой прогон стоп |

**Текущий статус (обновлять при смене):** `SMOKE_OK_RACE_UNVERIFIED` + `PENDING_PATH_HTTP_VERIFIED` — **не** полный `BLOCKER_CLEARED` по смыслу Стратега.
- Smoke #226 (`326d88ae…`): 1× payment; webhook при `succeeded`; ensure/skipped нет.
- Live closed-shift (`326d8c70…`, 2026-10-23): владелец закрыл смену → оплатил 1₽ → к webhook уже `receipt_registration=succeeded`, 1× payment без settlements, ensure в journal нет. **Pending не получен.** История: `docs/history/2026-10-23-smoke-pending-live-closed-shift.md`.
- HTTP: `test_webhook_http_pending_does_not_call_ensure_or_create_receipt` — ensure/create_receipt не вызываются при `pending`.
- Боевые 3/5/8k **возвращены**. Повторный SUPPORT 8000 — только по **«да, платим 8000»** с явным принятием остаточного риска гонки. Коррекция FD 778 — с бухгалтером.
- Деньги net: smoke 1₽ ×3 (#220+#226+closed-shift); не «8002 без возвратов».

### Пробел после #226 (stuck pending → canceled)

Webhook больше **не** ретраит при `pending`/`пусто` (анти-дубль). Если авточек invoice сорвётся в `canceled` **после** уже обработанного webhook — автоповтор **не** сработает.

| Есть сейчас | Нет |
|-------------|-----|
| CLI `python -m sfrfr yookassa-retry-receipt <payment_id> --email …` (тот же ensure + gate) | Job/timer reconcile зависших fiscal (`pending`→потом `canceled`) |
| Webhook retry только при `canceled` **в момент** webhook | Периодический опрос `receipt_registration` у paid без succeeded `type=payment` |

Follow-up (не в этом smoke): узкий reconcile **только** для paid с `reg=canceled` и без succeeded/pending receipt — либо ручной CLI по письму ЮKassa. Не создавать при `pending`. См. SFRFR-89.

## Связанные артефакты

- Механика малых сумм: `docs/history/2026-10-23-payment-5rub-8rub-links.md`
- Smoke дедуп #220: `docs/history/2026-10-23-smoke-dedup-220-1rub.md`
- Smoke дедуп #226 (после FAIL 8000): `docs/history/2026-10-23-smoke-dedup-226-1rub.md`
- Live closed-shift (pending не воспроизведён): `docs/history/2026-10-23-smoke-pending-live-closed-shift.md`
- Боевой DIAG 3000: `docs/history/2026-10-23-battle-diag-3000.md`
- Боевой DOCS 5000: `docs/history/2026-10-23-battle-docs-5000.md`
- Боевой SUPPORT 8000 (**FAIL**): `docs/history/2026-10-23-battle-support-8000.md`
- Возврат 3/5/8k: `docs/history/2026-10-23-battle-refund-3000-5000-8000.md`
- Касса / дубли: SFRFR-89
- UI резюме + офер 3000: PR #214 / staff «Проверить документы»
- Фикс дублей ensure/retry: PR #220 (на 8000 дубль снова — gate неполный / второй путь фискализации)
