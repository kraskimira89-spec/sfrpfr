# Контрольный отчёт: MAX E05/F04 wire (изолированная интеграция)

```text
PR / head:
  https://github.com/kraskimira89-spec/sfrpfr/pull/263
  feat/sfrfr-110-max-e05-f04-wire (обновлять после push)
Зависимость от #261:
  Вариант 1 — stacked PR поверх точного head #261
  SHA: 71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01
  (docs/client-ai-dialogue-quality). Политики не копируются.
  После согласованного merge #261 — перебазировать на main + CI.
Фактический входной handler:
  sfrfr.integrations.max.handler → reply_to_free_text (свободный текст MAX)
Место вызова политики:
  llm_chat.reply_to_free_text (после staff_dialog_active, до LLM)
  → max_e05_f04_path.try_policy_reply_for_case
  → deliver_policy_reply_via_outbox (action=max_e05_f04_policy)
Источник подтверждения ошибки:
  TrustedErrorContext.error_confirmed через TrustedErrorContextPort
  Production-default: NullTrustedErrorContextAdapter → None (нет перехвата)
  Тесты: InMemoryTrustedErrorContextAdapter.put(...)
Источник результата ограничения:
  TrustedErrorContext.limit_op: TrustedOpResult (source=system-ack и т.п.)
  Срез НЕ вызывает установку ограничения; только читает исход.
Проверка принадлежности и версии:
  TrustedErrorContext.belongs_to / version_is_current
  InMemory отсекает чужой case и устаревший result_version
Проверка текста и attachments:
  build_e05_f04_outbound + F04_UNCERTAINTY_TEMPLATE
  _strip_incompatible_attachments при fallback / неуспехе меры
Сохранение и outbox:
  case_chat_delivery.enqueue_max_delivery
  process_now → process_pending_outbox или mock bot.send_message
Что подтвердил mock MAX:
  transport dict {ok: True, message_id: ...}; enqueue ≠ sent ≠ read
Команды тестов и результаты:
  .\.venv\Scripts\python.exe -m pytest tests/unit/test_max_e05_f04_wire_path.py tests/unit/test_max_sfrfr110_e05_f04_slice.py -q
  → 25 passed
Оставшиеся обходы:
  docs/ops/sfrfr-110-max-outbound-coverage.md (канон)
  docs/ops/max-e05-f04-remaining-bypass-map.md (указатель)
Риски доставки, вынесенные отдельно:
  docs/ops/max-e05-f04-delivery-risks.md
E01 readiness:
  docs/ops/sfrfr-110-e01-readiness.md — хранение/контракт, не фиктивное «исправлено»
```


Итог (с ограничениями):

> Доказан выбранный путь с тестовым источником фактов и подменёнными
> инфраструктурными зависимостями. Производственная обработка E05 из
> долговременного источника фактов ещё не подтверждена.

> Fake enqueue/bot не подтверждает реальную запись в outbox, транзакционность
> и поведение настоящего транспортного клиента.

Не утверждается: «MAX защищён полностью», «SFRFR-110 готова».

Контрольная точка после среза:

- Null/fallback: `docs/ops/sfrfr-110-null-fallback-delivery-check.md`
- Callback-карта: `docs/ops/sfrfr-110-max-callback-coverage.md`
- E01 контракт: `docs/ops/sfrfr-110-e01-operation-contract.md`
- Следующий PR: `docs/ops/sfrfr-110-next-pr-proposal.md`
