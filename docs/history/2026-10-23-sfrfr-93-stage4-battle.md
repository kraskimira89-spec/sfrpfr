# Этап 4: один боевой CLI (gate без POST)

## Подготовка

- Timer `sfrfr-fiscal-reconcile` **stopped + disabled**
- Среди 7: только `d41bd2ce` имел `receipt_registration=canceled` + succeeded type=payment → путь gate
- Остальные 6: `reg=succeeded` → job делает `skip_reg` без `fiscal_status=registered`

## CLI `yookassa-retry-receipt` id8=`d41bd2ce`

1. action=`gate_succeeded` (create не вызывался)
2. Повтор после lease 120 с: снова `gate_succeeded` (второго чека нет)
3. БД после: `fiscal_status=registered`, `reconcile_attempts=0`,
   `reconcile_last_outcome=succeeded`, `reconcile_post_payload` NULL, streak=0

## Follow-up данных

Остальные 6 с уже успешным чеком (reg=succeeded) помечены `fiscal_status=registered`
по одной строке — та же семантика, что gate. Иначе в бою вечный `skip_reg` в окне.

## Tracker

Запись: этап 4 — один существующий чек type=payment, POST не создавал новый.
