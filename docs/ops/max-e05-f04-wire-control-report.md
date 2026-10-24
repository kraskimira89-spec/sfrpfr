# Контрольный отчёт: MAX E05/F04 wire (изолированная интеграция)

```text
PR / head:
  (заполняется после push; ветка feat/sfrfr-110-max-e05-f04-wire)
Зависимость от #261:
  Вариант 1 — stacked PR поверх точного head ветки docs/client-ai-dialogue-quality.
  Политики #261 не копируются в этот PR; base = docs/client-ai-dialogue-quality.
  После merge #261 — перебазировать этот PR на main.
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
  .\.venv\Scripts\python.exe -m pytest tests/unit/test_max_e05_f04_wire_path.py -q
Оставшиеся обходы:
  docs/ops/max-e05-f04-remaining-bypass-map.md
Риски доставки, вынесенные отдельно:
  docs/ops/max-e05-f04-delivery-risks.md
```

Итог: **доказан один MAX-путь E05/F04 в изолированной интеграции**.

Не утверждается: «MAX защищён полностью», «SFRFR-110 готова».
