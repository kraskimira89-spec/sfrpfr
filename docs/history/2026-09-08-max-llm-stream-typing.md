# MAX LLM: typing pulse + псевдо-стрим (2026-09-08)

## Что сделано

Клиентский свободный текст в MAX (ТЗ-26):

1. **Typing pulse** — периодический `typing_on`, пока DeepSeek генерирует ответ (`MAX_LLM_TYPING_PULSE_*`).
2. **LLM stream** — `chat.completions` с `stream=True` во внутреннем контуре.
3. **Псевдо-стрим в чате** — placeholder + `PUT /messages` (edit) по мере текста; кнопки воронки только в финальном edit. Лимит MAX: ≤2 edit/сек → интервал ≥0.6 с.

Настоящего token-bubble стрима у MAX нет; UX = «печатает» + растущий текст в одном сообщении.

## Env

```env
MAX_LLM_TYPING_PULSE_ENABLED=1
MAX_LLM_TYPING_PULSE_SECONDS=3
MAX_LLM_STREAM_EDIT_ENABLED=1
MAX_LLM_STREAM_EDIT_MIN_INTERVAL_SECONDS=0.6
```

## Код

- `src/sfrfr/ai/llm.py` — `stream` / `on_partial`
- `src/sfrfr/integrations/max/client.py` — `edit_message`
- `src/sfrfr/integrations/max/llm_chat.py` — `TypingPulse`, `deliver_free_text_reply`, `stream_preview_text`
- `handler.py` — доставка через `deliver_free_text_reply` (+ фикс early-return rule reply)
