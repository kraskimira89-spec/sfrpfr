# Контракт хранения и операции E01 (без миграций)

Цель: «дата исправлена» только после подтверждённого сохранения.
Не фиктивный `persist_ok` из модели. Миграции и production-адаптер — только после согласования.

Зависимость контекста: #263 / #261 SHA `71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01`.

## Таблица: необходимый факт → источник → проверка → пробел → решение

| Необходимый факт | Существующий источник | Способ проверки | Пробел | Предлагаемое решение |
|---|---|---|---|---|
| Исходная дата / период в деле | `cases` snapshot / `ils_periods` / `labor_periods` / findings в `CaseRepository` snapshot fields | Чтение row + audit log | Нет единого «поля даты утверждения» с версией для клиентского E01 | Минимально: операция над конкретной записью периода с `id` + `version`; без новой таблицы — JSON patch + audit event |
| Источник значения (OCR / клиент / специалист / система) | OCR texts в snapshot; chat messages; staff edits разрознены | По source tag в событии | Нет обязательного `value_source` на периоде | Контракт события: `source ∈ {ocr_extract, client_said, staff_verified, system_derived}` |
| Различие OCR vs слова клиента vs проверенное | Текст OCR vs `case_messages` vs findings | Ручное/staff сравнение; библиотека deception сравнивает флаги | Нет API «verified_value» отдельно от OCR | Поле/ключ `verified_start` только после staff/system ack; OCR остаётся `ocr_start` |
| Право на изменение даты | Staff cabinet / admin; клиентский чат даты не пишет как SoT | RBAC staff | Клиентский LLM не должен писать дату | Запрет write из MAX LLM; только staff/job с actor_id |
| Версия при конкурентном изменении | `updated_at` на case/snapshot; нет optimistic lock периода | Сейчас last-write-wins | Нет `expected_version` в update | Минимально: `IF version = N THEN N+1 ELSE conflict`; без миграции — хранить version в JSON периода + отказ при mismatch |
| Прежнее значение и основание исправления | `audit(...)` в CaseRepository (события есть) | audit trail | Нет структурированной evidence-card «было→стало→почему» | Событие `period_date_corrected` с before/after/reason/actor/source; без новой таблицы — `case_events` / audit payload |
| Подтверждение записи | `TrustedOpResult` + `persist_flag_is_trusted` (`db_write_ack`, `repository_update_ok`, `job_event_persisted`) | library #261 | **Нет wire** записи даты → TrustedOpResult | Адаптер: после успешного repo update вернуть TrustedOpResult; LLM-флаги запрещены |
| Зависимые расчёты / отчёты / проекты | findings, draft, analysis_notes, клиентские ответы | Нет реестра зависимостей | Не размечено, что инвалидировать | Список `depends_on_period_date` в контракте операции; статус «на проверке» без «пенсия изменена» |
| Идемпотентность повторной операции | Частично outbox message_id; нет для period patch | — | Повтор может создать второе «исправление» | Ключ идемпотентности `op_id` / `(case_id, period_id, to_value, reason_hash)` |
| Неизвестный исход сохранения | `TrustedOpResult.ok=None` + outbox guards UNKNOWN_AFTER_ACCEPT | library | Нет UX/handler для E01 unknown | Не говорить «дата исправлена»; маршрут повторной проверки статуса записи |

## Ответы на 9 контрольных вопросов

1. **Где хранится исходная дата и источник** — в snapshot периодов дела (`ils_periods` / `labor_periods` / findings) и OCR-текстах; единого SoT-поля «утверждённая дата для клиента» нет.
2. **OCR vs клиент vs проверенное** — сейчас смешаны; контракт требует раздельных ключей до E01-wire.
3. **Кто вправе изменить** — только staff/system job с actor; не MAX LLM.
4. **Версия при конкуренции** — предложить version на записи периода; иначе conflict.
5. **Прежнее значение и основание** — audit/event payload before/after/reason.
6. **Чем подтверждается запись** — TrustedOpResult из реального repo ack, не LLM.
7. **Зависимые артефакты** — findings/draft/ответы; помечать «на проверке», не «пенсия пересчитана».
8. **Повтор операции** — идемпотентный ключ; второе нажатие не пишет заново при том же результате.
9. **Неизвестный исход** — запрет клиентского «дата исправлена»; отдельный recovery, не слепой retry.

## Минимальный следующий шаг (без миграции)

Оформить **read-only audit PR**: инвентаризация фактических write-путей периода/даты + черновик события `period_date_corrected` на существующих audit/API без изменения схемы БД.  
Если JSON version окажется недостаточен — **отдельное** предложение миграции с обоснованием (не в том же PR).

## Не делать сейчас

- Фиктивный `date_persist_succeeded=true` в тестах как «готово к prod».
- Merge #261/#263, deploy, live MAX.
- Полный E01 reply-path до появления реального ack записи.
