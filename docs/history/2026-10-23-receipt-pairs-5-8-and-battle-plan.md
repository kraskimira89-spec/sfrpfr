# 2026-10-23 — пары чеков 5/8 ₽, касса 759–761, smoke #214, план боевого

**Вердикт (формулировка для Стратега):** механика webhook→paid и чеков подтверждена на малых суммах; полные суммы не прогонялись.
**Не писать:** «тарифы приняты» / «5000/8000 приняты».

## 1. Расшифровка пар FD (shop 1421177, ПС-878680)

Payment ids из `2026-10-23-payment-5rub-8rub-links.md`. API `GET /v3/receipts?payment_id=…`.

### DOCS 5₽ — payment `326d4ecc…03b4`, charge **5.00**, `receipt_registration=succeeded`

| FD | type | status | сумма позиции | settlements | registered_at (API) |
|----|------|--------|---------------|-------------|---------------------|
| **770** | **payment** | succeeded | **5.00** | cashless 5.00 | 2026-10-23T07:47:00Z |
| **771** | **payment** | succeeded | **5.00** | null | 2026-10-23T07:47:00Z |

### SUPPORT 8₽ — payment `326d4ef1…7321`, charge **8.00**, `receipt_registration=succeeded`

| FD | type | status | сумма позиции | settlements | registered_at (API) |
|----|------|--------|---------------|-------------|---------------------|
| **772** | **payment** | succeeded | **8.00** | cashless 8.00 | 2026-10-23T07:47:00Z |
| **773** | **payment** | succeeded | **8.00** | null | 2026-10-23T07:47:00Z |

**Вывод для Стратега:** это **не** нормальная пара приход+возврат (`type=refund` нет). Оба чека в паре — `type=payment` / `succeeded` на один payment_id → **дубль того же класса, что FD 759–761**. Суммы позиций совпадают с 5.00 / 8.00. Разбор — касса/Evotor (SFRFR-89).

## 2. Дубли FD 759–761 (SFRFR-89)

| Поле | Факт |
|------|------|
| Задача | [SFRFR-89](https://tracker.yandex.ru/SFRFR-89) «Касса: дубли FD 759–761 + коррекция Evotor» |
| Статус | Открыт; assignee Проверка Стажа |
| Передача | **Да** — комментарий 2026-10-23 (подтверждение передачи ответственному за кассу) |
| Срок | **2026-10-28** |
| API (shop **1417002**, старый) | FD **759, 760, 761** — все `type=payment` / succeeded, один payment `326bea92…0fe4`, суммы позиций **3000.00** |

## 3. Smoke честного резюме + офер 3000 (#214)

| Поле | Факт |
|------|------|
| Дело | **ПС-647587** / CASE-2026-647587 (`d503add3-…e1a3`, `is_test`) — **новое** |
| Staff path | `honest_brief`: 3 пункта, статусы docs/needs_check (+ система client), все с основанием |
| Офер 3000 | `offer_diag_allowed=true`, amount **3000** только при justified + docs\|needs_check |
| Негатив | client-only → офер **запрещён** (unit + live payload) |
| Платёж 3000 | **не** создавался |
| MAX web | открыт чат существующего user; **не** = новое дело без отдельного `max_user_id` |
| Unit | `test_honest_brief_ui_*` — 3 passed |

Admin: `https://admin.proverkastaza.ru/c/d503add3-956a-48bc-91dc-1c3c3579e1a3?view=cases`

## 4. План боевого прогона

Файл: `docs/ops/plan-battle-payment-run-3000-5000-8000.md`
Порядок DIAG 3000 → DOCS 5000 → SUPPORT 8000; shop 1421177; ENABLED=0; Evotor online; владелец денег TBD; без пакета «анализ+обращения 5k».
