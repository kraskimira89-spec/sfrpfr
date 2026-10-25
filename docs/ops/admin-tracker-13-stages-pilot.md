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

- [x] Код: `TRACKER_CASE_SYNC_ALLOWLIST` + `PostgresTrackerOutboxStore` + enqueue/tick API (волна C)
- [ ] Выбрать одно тестовое дело и прописать uuid в allowlist на VPS
- [ ] Локальные поля CASE + `TRACKER_CASE_FIELD_IDS_JSON`
- [ ] Карточка CASE + `issue_key` (или `case_tracker_issues.issue_type=case_dispatch`)
- [ ] Dry-run: enqueue → tick на allowlist-деле
- [ ] Повтор того же event_id не дублирует задачу
- [ ] Ошибка API Трекера → status=error в outbox, дело в БД цело
- [ ] Глобальный `TRACKER_CASE_SYNC_ENABLED` — только после зелёного пилота (отдельное решение)
