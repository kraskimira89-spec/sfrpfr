# MAX bot_owned: диалог без сотрудника до «Позвать специалиста»

## Сделано

1. `MAX_BOT_OWNED_ENABLED` / `MAX_BOT_OWNED_PAY_LINK` — режим до специалиста.
2. После оператора LLM не отвечает (`waiting_for_staff`).
3. Старт и файлы в bot_owned не создают staff-задачу / ops-пинг.
4. Фразы и soft-кнопки канона шага → `intake:` FSM.
5. Лимит `MAX_LLM_CHAT_MAX_TURNS` на intake.
6. После ingest — статус комплекта без OCR; ИЛС+трудовая → оферта DIAG 3000 ₽.
7. Pay link в MAX после `contract_accepted` (точечно, не глобальный AUTO_SEND).

## Файлы

- `src/sfrfr/integrations/max/bot_owned.py`
- `src/sfrfr/integrations/max/intake_from_text.py`
- `src/sfrfr/services/max_kit_status.py`
- `src/sfrfr/services/max_bot_invoice.py`
- handler / llm_chat / ingest_worker / case_repository / config
