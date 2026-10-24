# SFRFR-110: карта покрытия MAX outbound

Карта описывает покрытие срезом E05/F04 (#263), а не разрешает обход проверок.
Поиск: `MaxBotClient` / `send_message` / `enqueue_max_delivery` / `process_pending_outbox`
в `src/` (2026-10-24). Один файл ≠ полный контур; обновлять при новых вызовах.

## Зависимость среза

| Поле | Значение |
|---|---|
| PR | #263 → base `#261` (`docs/client-ai-dialogue-quality`) |
| SHA зависимости #261 | `71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01` |
| Покрытый путь | свободный текст → `reply_to_free_text` → E05/F04 → outbox/mock |
| Канон ошибок | main после #262 |

**Граница теста:** проверка начинается после входной аутентификации и первичной
маршрутизации webhook; эти участки тестом E05/F04 не покрыты. Это не полный webhook E2E.

**Fake-инфраструктура:** InMemory adapter + mock `enqueue`/`bot` — реальные
ограничения БД, транзакции и конкурентность outbox **не** проверены.

## Покрыто срезом

```text
Путь / назначение: свободный MAX-диалог, один кейс E05/F04
Файл::функция: integrations/max/llm_chat.py::reply_to_free_text
  → services/max_e05_f04_path.py::try_policy_reply_for_case
  → handler.py (ветка action=max_e05_f04_policy)
  → deliver_policy_reply_via_outbox → case_chat_delivery.enqueue_max_delivery
Кто вызывает: handler свободного текста после staff_dialog check
Источник текста: F04_UNCERTAINTY_TEMPLATE / ERROR_NOT_CONFIRMED (не LLM)
Проверка пользователя и дела: case_id + TrustedErrorContext.belongs_to / version
Источник системных фактов: TrustedErrorContextPort (prod: Null → нет перехвата)
Проверка текста и кнопок: build_e05_f04_outbound + strip inline_keyboard
Outbox или прямой send: enqueue; process_now / mock bot
Идентификатор операции: TrustedErrorContext.operation_id
Проверка актуальности перед отправкой: result_version в адаптере
Поведение при неизвестном исходе: limit_outcome=unknown; меру не утверждать
Тест: tests/unit/test_max_e05_f04_wire_path.py
Пробел: prod-источник фактов ещё Null; webhook auth вне теста
Связанная задача: SFRFR-110 / #263
```

## Не покрыто (исходный перечень + найденные функции)

### Rule-bot / статусные ответы

```text
Путь / назначение: статус дела / шаблоны без LLM
Файл::функция: integrations/max/handler.py::_reply_from_case_status; _reply
Кто вызывает: ветки сценария анкеты / кнопок
Источник текста: шаблоны handler / intake
Проверка пользователя и дела: case_id из сессии (нужна инвентаризация)
Источник системных фактов: нет TrustedErrorContext
Проверка текста и кнопок: нет E05/F04 gate
Outbox или прямой send: _reply → bot.send_message (прямой)
Идентификатор операции: нет
Проверка актуальности перед отправкой: частичная (статус дела)
Поведение при неизвестном исходе: не формализовано
Тест: вне среза
Пробел: источники статусов и прямая отправка
Связанная задача: SFRFR-110 follow-up outbound inventory
```

### Callback / soft-ask

```text
Путь / назначение: payload кнопок, soft-ask, офферы
Файл::функция: handler.py (payload handlers); max_bot_funnel.py enqueue
Кто вызывает: callback update
Источник текста: шаблоны воронки
Outbox или прямой send: enqueue_max_delivery и/или _reply
Пробел: повтор клика, актуальность offer, отказ
Связанная задача: отдельный PR soft-ask / offer gates
```

### Приём файлов

```text
Путь / назначение: ack загрузки документа
Файл::функция: integrations/max/document_background.py (enqueue_max_delivery);
  attachment_lifecycle.py (MaxBotClient)
Кто вызывает: media/document pipeline
Пробел: сохранение ≠ читаемость ≠ проверка; нет E05
Связанная задача: docs/file quality path
```

### Brief / отложенное резюме

```text
Путь / назначение: brief_analysis → MAX
Файл::функция: services/brief_analysis.py (~enqueue_max_delivery)
Пробел: версия результата и допустимость кнопок
Связанная задача: SFRFR-110 brief outbound
```

### Фоновые / нейтральные уведомления

```text
Путь / назначение: notify, reactivation, neutral chat ping
Файл::функция:
  case_chat_delivery.py (mirror / neutral notify / staff mirror)
  case_reactivation.py (enqueue + прямой send_message)
  integrations/client_channels/notifications.py
  integrations/payments/notify.py
  services/case_chat_payment.py
Пробел: настройки канала, актуальность перед send, учёт отправки
Связанная задача: delivery risks block
```

### Кабинет / Staff → MAX

```text
Путь / назначение: admin/portal зеркало в MAX
Файл::функция:
  api/routes/admin_portal.py (enqueue + process_pending_outbox)
  api/routes/portal.py (process_pending_outbox; login confirm send)
  case_chat_delivery.py::mirror_* / process_pending_outbox
Пробел: авторство staff, прямой fallback, принадлежность получателя
Связанная задача: staff delivery audit
```

### Инвойс / pay-link / пост-диагностика

```text
Путь / назначение: коммерческие и сервисные шаблоны
Файл::функция:
  max_bot_invoice.py; pay_link.py; max_post_diagnosis.py; max_kit_status.py
Outbox или прямой send: enqueue и/или MaxBotClient.send_message
Пробел: совместимость кнопок с E-политиками
Связанная задача: offer/policy gate per path
```

### Ops / fiscal / CLI / channel review

```text
Путь / назначение: ops-бот, фискальные алерты, CLI send, channel_review
Файл::функция:
  fiscal_reconcile_job.py; cli/main.py; ops_bot.py;
  channel_review.py; lead_ops_notify.py; lead_emergency_buffer.py
Пробел: не клиентский E05; всё же outbound MAX
Связанная задача: ops outbound inventory (отдельно от client AI)
```

### Retry outbox / аварийные fallback

```text
Путь / назначение: process_pending_outbox; max_outbox_guards
Файл::функция: case_chat_delivery.py::process_pending_outbox;
  max_outbox_guards.py; api/routes/max_webhook.py (process_pending_outbox)
Пробел: конкуренция, UNKNOWN_AFTER_ACCEPT, частичное сохранение
Тест: test_max_sfrfr110_e05_f04_slice (classify) + wire stages
Связанная задача: docs/ops/max-e05-f04-delivery-risks.md
```

## Как подтвердить полноту (чеклист)

1. [x] Grep `MaxBotClient` / `send_message` / `enqueue_max_delivery` в `src/`
2. [x] Отметить webhook `process_pending_outbox` триггеры
3. [ ] Проследить каждый payload handler до `_reply` (детальная матрица callbacks)
4. [ ] Конфигурационные / динамические пути (feature flags)
5. [ ] Повторный grep после merge #261/#263

Карта **не полна** до пункта 3–4. Не утверждать «MAX защищён».

## Связанные документы контрольной точки

- Callback subcodes: `docs/ops/sfrfr-110-max-callback-intake-q-subcodes.md`
- Null→LLM gap: `docs/ops/sfrfr-110-null-llm-gap.md`
- Period-date audit: `docs/ops/sfrfr-110-period-date-write-audit.md`
- Test evidence: `docs/ops/sfrfr-110-test-evidence-registry.md`
