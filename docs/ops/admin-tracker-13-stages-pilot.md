# Пилот: проекция 13 ступеней в Яндекс Трекер

**Статус:** план пилота. Глобальный sync **выключен**. Production-миграции этим документом не согласованы.

## Цель

На **одном** `is_test` деле проверить: outbox → карточка CASE → отображение `currentStage` (13 id) → повтор события / ошибка / восстановление.

## Канон

- [docs/TRACKER/spec-case-dispatch-card.md](../TRACKER/spec-case-dispatch-card.md)
- [docs/TRACKER/architecture-tracker-sync-inbox-outbox.md](../TRACKER/architecture-tracker-sync-inbox-outbox.md)

## Правила

1. Трекер отражает подтверждённые факты БД, не создаёт оплату/подачу статусом.
2. Косвенные фразы чата — только подсказки в admin (см. `chat-signal-hints`), не факты для sync.
3. Включение sync на проде — отдельное решение владельца после пилота.

## Чек-лист пилота (когда разрешат)

- [ ] Выбрать одно тестовое дело
- [ ] Dry-run / флаг sync только для case_id
- [ ] Смена ступени в admin → событие outbox
- [ ] Повтор того же event_id не дублирует задачу
- [ ] Ошибка API Трекера → sync_status=error, дело в БД цело
- [ ] Восстановление reconcile
