# Синхронизация Трекер ↔ БД через outbox (срез 1)

**Дата:** 2026-10-25
**Задача:** [SFRFR-118](https://tracker.yandex.ru/SFRFR-118)
**Статус:** код клиента + outbox-worker проекции; webhook / prod-автодействия / очередь CASE **не** включались
**Канон разделения:** [spec-case-dispatch-card.md](spec-case-dispatch-card.md) (PR docs)
**Целевая схема inbox/outbox:** [architecture-tracker-sync-inbox-outbox.md](architecture-tracker-sync-inbox-outbox.md) · DDL `20261025130000_tracker_sync_schema.sql`

## Принцип

```text
Бизнес-факт в БД + событие outbox
        → Tracker sync worker обновляет проекцию карточки
Ошибка Трекера ≠ откат оплаты / документов
```

Обратный путь (webhook → inbox → команды) — **следующий срез**, не этот PR.

## Сопоставление с существующим кодом

| Было | Остаётся | Новое |
|---|---|---|
| `yandex_tracker/__init__.py` sync `create_issue` / STAZH | да | — |
| `quality_issues.py` из admin | да | — |
| — | — | `client.py` — async транспорт без write-retry |
| — | — | `projection.py` — поля проекции |
| — | — | `outbox.py` — enqueue + process |
| — | — | миграция `tracker_sync_outbox` |

Не подключать второй независимый OAuth-клиент.

## Env (по умолчанию sync выкл.)

```env
TRACKER_CASE_SYNC_ENABLED=0
TRACKER_CASE_QUEUE=          # пусто до решения владельца (CASE/DELO)
TRACKER_CASE_FIELD_IDS_JSON={"case_ref":"...","current_stage":"...","case_revision":"..."}
```

Идентификаторы локальных полей брать из фактической очереди, не из русских подписей UI.

## Контракт события outbox

```text
event_id          — неизменяемый; повтор с тем же телом идемпотентен
event_type        — payment_confirmed | …
case_ref / issue_key / case_revision
payload           — проекция без ПДн (stage, next_action, waiting_on, оплаты по услугам)
origin            — app
```

Worker при HTTP ≥500 на PATCH → `outcome_unknown`, событие остаётся `pending` (сверка), без «успеха».

## Что не в этом срезе

- `POST /integrations/tracker/commands` (inbox)
- автодействия Трекера и клиентские MAX-напоминания 3д
- автосоздание очереди CASE/DELO
- подтверждение оплаты/подачи статусом задачи

## Приёмка среза (unit)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_tracker_client.py tests/unit/test_tracker_projection_outbox.py -q --basetemp=tmp/pytest-tracker
```

Проверено локально: 9 passed (2026-10-25).

