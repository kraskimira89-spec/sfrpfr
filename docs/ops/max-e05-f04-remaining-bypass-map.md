# Карта оставшихся обходных путей MAX (после среза E05/F04)

Срез подключил политику только к `reply_to_free_text` при ненулевом
`TrustedErrorContextPort`. Ниже — пути, которые **ещё не** проходят E05/F04.

| Путь | Где | Риск |
|---|---|---|
| Кнопки / callback сценария | `handler` payload handlers | Свободный LLM/шаблон без TrustedErrorContext |
| Документ / upload ack | `max_document_upload` / handler media | Иной reply-path |
| Зеркало специалиста → MAX | `case_chat_delivery` staff outbox | Текст специалиста без policy gate |
| Инвойс / оферта | `max_bot_invoice` | Коммерческие кнопки рядом с сервисным текстом |
| Пост-диагностика | `max_post_diagnosis` | Отдельные шаблоны |
| Nudge / turn-limit / PDN block | `llm_chat` early returns | До перехвата E05 (ок по дизайну) |
| Staff-silent | `staff_dialog_active` | Политика намеренно не перехватывает |
| Cabinet / web chat | вне MAX | Вне скоупа среза |
| Прямой `MaxBotClient.send_message` | любые сервисы | Минуя outbox и policy |
| Null-адаптер (prod default) | `get_trusted_error_context_adapter` | Перехват не активен, пока нет реального источника фактов |

Обновлять при подключении следующих путей; не считать карту закрытой.
