# История: таблица контроля воронки MAX на Яндекс Диске

Дата: 2026-08-12

## Запрос

Завести простую таблицу контроля воронки MAX в Яндекс Диске (отдельная папка) или в amo.

## Решение

- Основное место: Яндекс Диск `disk:/SFRFR-ops/marketing-max-funnel/` (без ПДн).
- CSV с этапами Launchi + инструкция; в amo только агрегаты лидов/оплат за неделю.
- В `disk.py` добавлены `ensure_ops_path` и загрузка в подпапку `folder=`.

## Файлы

- `docs/marketing-sales/reports/max-funnel-weekly.csv`
- `docs/marketing-sales/reports/max-funnel-control.md`
- обновлены Launchi-док и README маркетинга
