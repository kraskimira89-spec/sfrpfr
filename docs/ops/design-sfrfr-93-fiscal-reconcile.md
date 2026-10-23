# SFRFR-93: fiscal reconcile — дизайн (без кода)

Дата: **2026-10-23**. Источник: разбор Стратега по `main` + ответы по путям в репо.
Код **не** стартовать без команды владельца («делаем SFRFR-93»).

## Цель

Тонкая обёртка над уже существующими `ensure_payment_receipt`, `payment_receipt_retry_gate`, `should_auto_retry_fiscal_receipt` — не новая логика фискализации.

## Три ловушки (канон)

1. **Пустой `receipt_registration`.** `ensure` пропускает только `succeeded`/`pending`; при пустом идёт к `GET /receipts` и может создать чек. Job **обязан** до вызова ensure проверить `should_auto_retry_fiscal_receipt(reg)` (истина только для `canceled`/`cancelled`) — иначе риск дубля как FD 777+778.
2. **`canceled` ≠ «чека нет».** После фискализации поле может остаться `canceled` (FD 770/771); решающий фильтр — gate по списку чеков внутри ensure.
3. **`Idempotence-Key` сейчас `uuid4` в `_post`.** Параллельные тики = два чека. Для reconcile нужен детерминированный ключ (`reconcile:{payment_id}:{attempt}`) + блокировка на платёж. TTL ключа ЮKassa — сверить с докой при реализации.

## Алгоритм (согласован)

Для кандидата: окно 48 ч / grace ≥2 мин → lock → backoff/attempts → `fetch_payment` → `should_auto_retry_fiscal_receipt` → иначе skip → `ensure_payment_receipt` (email/phone как webhook) → запись попытки → после 48 ч без succeeded receipt — алерт владельцу.

Флаг по умолчанию: `FISCAL_RECONCILE_ENABLED=0`. Первый этап — **dry-run** (лог «создал бы»), без `create_receipt`. Период: **каждые 10 мин**, отдельный systemd timer (не смешивать с `finance-due-tick`).

## Пути в коде (ответы на допущения)

| Вопрос | Ответ |
|--------|--------|
| Где платежи | Таблица `public.payments` (миграции `supabase/migrations/20260722122128_b2c_schema_rls.sql`, `…_payments_one_active_per_order.sql`). Поля: `status`, `provider_payment_id`, `paid_at`, `created_at`, `fiscal_status`, `order_id`. |
| Как достать за 48 ч | Готового list-by-window **нет**. Репозиторий: `src/sfrfr/db/case_repository.py` (`find_active_payment`, `create_payment_record`, mark succeeded…). Нужен **новый** метод вида `list_succeeded_payments(since, until)` по `status=succeeded` + `paid_at` (fallback `created_at`) + непустой `provider_payment_id`. |
| Email/телефон | Как webhook: `src/sfrfr/api/routes/payments.py` → `_retry_fiscal_receipt` читает `get_case_row` → `clients.email` / `clients.phone`. |
| CLI retry | `src/sfrfr/cli/main.py` → `yookassa-retry-receipt` (~1023): тонкий вызов `YooKassaClient().ensure_payment_receipt`. Логику ensure **не дублировать**. |
| Ensure / gate | `src/sfrfr/integrations/payments/__init__.py`: `ensure_payment_receipt`, `should_auto_retry_fiscal_receipt`, `payment_receipt_retry_gate`, `_post` (uuid4 Idempotence-Key). |
| Таймер finance | `docs/systemd/sfrfr-finance-due.timer` + `.service` → `python -m sfrfr finance-due-tick` (07:00 МСК). Логика: `src/sfrfr/services/finance_automation.py`. CLI: `src/sfrfr/cli/main.py` → `finance-due-tick`. Для reconcile — **отдельные** `sfrfr-fiscal-reconcile.timer` + CLI `fiscal-reconcile-tick`. |
| Тесты эталон | `tests/unit/test_yookassa.py` (ensure + webhook pending). |

## Тесты (минимум из разбора)

1. `reg=canceled`, нет чека → 1 create  
2. `reg=canceled` + succeeded payment receipt → skip `succeeded_payment_receipt_exists`  
3. `reg=pending` → skip  
4. `reg` пустой → skip, create **не** вызывается  
5. Два тика подряд → 1 чек (lock + backoff + idem key)  
6. Вне окна 48 ч / младше grace → skip  
7. Ошибка `list_receipts` → попытка записана, create нет  
8. Исчерпаны попытки → алерт, не бесконечный цикл  

## Критерий старта кода

Явная команда владельца: **«делаем SFRFR-93»** (или эквивалент). До неё — только этот дизайн + Tracker.
