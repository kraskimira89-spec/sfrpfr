# 2026-08-23 — MVP STAZH: кабинет → Яндекс Трекер

## Зачем

Отделить внутренние задачи качества от клиентских дел: кнопка в admin создаёт обезличенную задачу в очереди STAZH.

## Сделано

- `src/sfrfr/integrations/yandex_tracker/` — API client, sanitizer, case_ref, quality service
- `POST /admin/cases/{id}/tracker`, health, list
- Миграция `case_tracker_issues`
- UI модалка в admin
- Плагин `sfrfr-issue-wizard` + очередь STAZH
- Docs: `docs/ops/yandex-tracker-stazh-quality.md`
- Тесты: `tests/unit/test_yandex_tracker_quality.py`

## Env

`TRACKER_TOKEN`, `TRACKER_ORG_ID`, `TRACKER_QUEUE=STAZH`, `TRACKER_CASE_REF_SECRET`
