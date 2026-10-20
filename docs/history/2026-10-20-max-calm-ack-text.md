# 2026-10-20 — MAX: спокойный текст ack вместо FALLBACK_MENU

## Проблема

После фикса «одно сообщение на пачку» клиент всё ещё получал старый
`FALLBACK_MENU_TEXT` («Спасибо за сообщение… кнопками ниже… заказать звонок»),
потому что медиа без url шло в ветку пустого апдейта с меню и кнопками.

## Решение

- Пустой апдейт без скачанных байтов → всегда `processing_ack_text()` и
  `claim_processing_ack`, без goal_keyboard / FALLBACK.
- Текст: время на обработку + «не торопитесь присылать всё подряд».
- Убрана debug-инструментация session 7466db (handler/webhook/document_background).

## Проверка

- `pytest tests/unit/test_max_media_fallback_no_spam.py tests/unit/test_max_docs_quiet_batch.py` — 7 passed.
- После деплоя: вложение в MAX → одно сообщение про разбор, не FALLBACK.

## Ветка / PR

`fix/max-calm-ack-text` (supersedes cleanup PR #160).
