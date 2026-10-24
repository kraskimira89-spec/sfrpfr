# SFRFR-110: единая матрица E/F покрытия (этап 1)

Канон: `docs/specs/client-ai-error-response-catalog.md`,  
F: `docs/qa/client-ai-error-scenarios.md`,  
индекс: `docs/specs/client-ai-error-docs-index.md`.

**DoD:** не «библиотека + один путь». Закрытие — только при реальных источниках,
проверенных выходах и принятой матрице. Этот документ — контрольный список;
статусы ниже — фактические на 2026-10-24 (перепроверить перед close).

Легенда статуса:

| Код | Смысл |
|---|---|
| `LIB` | Политика/шаблон в library (#261), без wire |
| `WIRE_ISO` | Изолированный wire + InMemory/mock |
| `FILTER` | Лексический постфильтр max_llm_reply (#266), не полный E-кейс |
| `AUDIT` | Аудит есть, операции нет |
| `GAP` | Нужна реализация |
| `N/A?` | Кандидат в неприменимо — **требует принятия на ревью**, не самозакрытие |

Блокеры close: **E01**, **E05/F04 prod adapter**, outbound map close, доставка UNKNOWN.

---

## E01–E21

| ID | Требование (канон) | Применимость | Источник фактов | Проверки | Разрешённый ответ | Неопределённость | Точки выхода (сейчас) | Проверка | Остаток / блокер close? |
|---|---|---|---|---|---|---|---|---|---|
| E01 | Дата после persist | Периоды ИЛС/трудовая | `case_pipeline_data` periods; **нет** точечной op | дело, period, version, actor | «Дата исправлена» только после ack | persist не завершён | нет клиентского wire | audit #265 | **GAP — блокер**; next PR = date op |
| E02 | Необоснованная сумма | Ответы с «прибавкой» | нет SoT суммы пенсии | — | снять статус суммы | — | LLM prompt / filter частично | LIB | GAP; не плодить калькулятор |
| E03 | Ложный «проверка выполняется» | статусы дела | `pipeline_status` / jobs | queued≠running | сопоставить с SoT | — | `client_case_status`, rule-bot | частичный SoT | GAP wire честного исправления лжи |
| E04 | Ошибка → оплата | после оплаты | претензия/номер | регистрация | номер **или** честный сбой | — | claim path? | LIB | GAP; не авто-возврат |
| E05 | Последствия неизвестны | ошибка + impact unknown | TrustedErrorContext | дело, version, limit_op | F04-текст без фиктивной отметки | Null / нет фактов | `reply_to_free_text` + #263 | WIRE_ISO + LIB | **prod adapter GAP — блокер** |
| E06 | Финал после последствий | после E05 | статусы зависимостей | — | перечень + открытое | — | нет | LIB | GAP |
| E07 | Фамилия/реквизит | OCR vs verified | docs / findings | личность | правка поля | чужой документ | нет точечной op | GAP | как E01-паттерн |
| E08 | «Пропущенный период» | findings | findings + docs | не категоричность | смягчение / «нельзя утверждать» | мало оснований | brief/findings notify | LIB/FILTER частично | GAP |
| E09 | Классификация основания | evidence labels | evidence tags | — | метка исправлена | — | LIB | GAP wire |
| E10 | Арифметика | внутренние расчёты | если есть calc | — | исправление расчёта ≠ пенсия | спорный метод | N/A? если нет calc в продукте | **N/A? ревью** | не выдумывать calc |
| E11 | Неактуальный результат | версии проверки | snapshot version | version | старая неактуальна | — | partial version в TrustedErrorContext | GAP | |
| E12 | Рекомендация/срок/подача | советы в чате | — | позиция подачи | уточнение; не автоподача | неизвестные последствия | prompt + submission-position | FILTER слабо | GAP |
| E13 | Цена/состав услуги | офферы 3/5/8 | gates/orders | — | проверить условия; не крутить оффер | — | offer callbacks | partial gates | GAP E13-текст |
| E14 | Повтор запроса документа | upload state | documents | доступ vs запись | не просить весь комплект | запись есть, доступ нет | doc_bg / kit status | partial | GAP |
| E15 | Handoff специалисту | operator/callback | ticket/assignment | регистрация ≠ назначение | честный статус | — | `_handle_operator` | GAP «уже занимается» | блокер ложных handoff |
| E16 | Выдача результата | PDF/доступ | storage/ACL | доступ ≠ ознакомление | выдача не завершена | — | post_diagnosis / cabinet | GAP | |
| E17 | Уведомления после отказа | marketing/opt-out | consent flags | — | ошибка повторной рассылки | — | marketing consent | partial | GAP |
| E18 | Преждевременное закрытие | pipeline_status | status SoT | — | фактическое состояние | — | status replies | GAP | |
| E19 | Оплата/возврат без op | payments | YooKassa/ledger | unknown ≠ fail/ok | не повторять без сверки | unknown | payments notify | GAP + delivery | связан F01/E19 |
| E20 | Чужие данные | инцидент | security route | — | защищённый маршрут | до подтверждения | нет универсального текста | GAP | не «удалено, риска нет» |
| E21 | Базовый шаблон | общий | факты кейса | — | конкретная ошибка + шаг | нет фактов → safe | LIB | GAP wire | |

## F01–F04

| ID | Требование | Применимость | Источник | Точки выхода | Статус | Остаток |
|---|---|---|---|---|---|---|
| F01 | Отказ регистрации ≠ успех | претензии/заявки | registration ack | claim paths | LIB | GAP wire |
| F02 | Сопровождение ≠ закрытие пенсии | статусы заказа | order vs pension | status texts | LIB | GAP |
| F03 | Исправленное дело при открытом дефекте | E06/E01 deps | defect flags | — | LIB | GAP |
| F04 | Неопределённость без успешной отметки | E05 | limit_op fail/unknown | #263 path | WIRE_ISO | **prod adapter блокер** |

## Outbound (сводка; детали в картах)

| Путь | Документ | Покрытие E/F | Блокер close? |
|---|---|---|---|
| free-text LLM | #266 filter + #263 E05 | FILTER + WIRE_ISO | да, до prod facts |
| callback intake/q | `sfrfr-110-max-callback-*.md` | не E-policy | да |
| rule-bot / status | handler `_reply_from_case_status` | partial SoT | да |
| docs/files | document_* | нет E | да |
| brief / funnel | brief_analysis, max_bot_funnel | нет E | да |
| cabinet/staff → MAX | case_chat_delivery, admin | нет E-policy на текст | да (правила staff отдельно) |
| outbox retry | max_outbox_guards | classify UNKNOWN | да, блокирующие риски |

## Правила матрицы

1. Не выдумывать кейс по ID — читать каталог.
2. `N/A?` только с обоснованием + принятие ревью.
3. Нет операции ≠ неприменимо, если сценарий согласован.
4. Не создавать финансы/тарифы ради покрытия.

## Следующие шаги матрицы

1. Принять/отклонить `N/A?` (E10 и др.) на ревью.
2. После date-op PR — обновить строку E01.
3. После prod adapter — E05/F04 → не WIRE_ISO.
4. Дописать `файл::функция` по мере закрытия outbound inventory.
