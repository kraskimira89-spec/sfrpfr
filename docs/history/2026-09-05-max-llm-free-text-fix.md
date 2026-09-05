# 2026-09-05: MAX — произвольный текст и LLM-чат

## Проблема

1. Коммит `22e0b062` сбил отступы в `handler.py` / `portal.py` → SyntaxError, деплой падал на lint.
2. При UUID-деле свободный текст уходил в `bot_reply_queued` без синхронного ответа ТЗ-26 (кнопки воронки).
3. До создания дела — только `free_text_nudge`, без LLM.
4. Health показывал только `ops_llm_*`, не клиентский `llm_chat`.

## Исправление

- Восстановлены отступы (откат поломки `22e0b062`).
- MAX free text: rule-reply → сразу `reply_to_free_text` (не queue); очередь остаётся у portal.
- До дела: тоже `reply_to_free_text`.
- Health: `llm_chat_enabled`, `llm_chat_model`.

## Проверка

- `pytest tests/unit/test_max_llm_chat.py tests/unit/test_max_intake.py` — OK.
- Ручной MAX: свободный текст → ответ + кнопки шага; диагностика 3 000 ₽ в промпте.
