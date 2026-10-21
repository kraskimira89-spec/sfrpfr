# 2026-10-21 — Аудит вызовов DeepSeek (без ПДн)

Срез по коду на `main` после SFRFR-81 (#162). Секреты и тексты сообщений не приводятся.

## Пути вызова

| Путь | Модуль | Клиент LLM | Модель (канон) | Thinking | История |
|---|---|---|---|---|---|
| Клиентский MAX free-text | `integrations/max/llm_chat.py` → `reply_to_free_text` | `LLMClient.for_analyze(allow_fallback=False)` | Yandex AI Studio `gpt://{folder}/deepseek-v4-flash` | Не включается явно; YC DeepSeek может писать `reasoning_content`, в коде есть fallback на него | До 20 реплик `case_messages` через `fetch_recent_case_messages` |
| Soft-кнопки / fallback | тот же путь; при сбое → `free_text_nudge` | — | — | — | — |
| Suggest специалисту | `services/staff_reply_suggest.py` + `admin_portal` `/suggest-replies` | тот же YC DeepSeek | analyze | как выше | последние ~40 сообщений (после #155) |
| Ops-бот | `integrations/max/ops_bot.py` | `LLMClient.for_ops_dialog` | `max_ops_llm_model` | как выше | свой контур ops |
| Кабинет bot_reply queue | `portal` → `enqueue_bot_reply_job` | отдельный worker | YC | — | case chat |

Прямой `platform.deepseek.com` в production **не** используется (`allow_fallback=False` у клиентского чата; fallback только вне prod при флаге).

## Что передаётся в клиентский ответ (до ContextPack)

- System: длинный `CLIENT_CHAT_SYSTEM` (тон, тарифы, запреты).
- User: `build_client_llm_user_prompt` — канал, `format_deal_context(work)`, шаг intake, история (до 400 символов/реплика, redact), новое сообщение.
- **Не** передавались явно: подтверждённые поля анкеты, available/pending/failed вложений, флаг «специалист активен», запрет имитировать чтение файла.

## Лимиты

- Timeout HTTP: 60s для YC DeepSeek, иначе 20s.
- `max_tokens=2048` для deepseek на YC.
- Клиентский ответ обрезается ~700 символов после parse REPLY.
- `max_llm_chat_max_turns` (по умолчанию 5) → fallback на кнопки.

## Разделение suggest vs клиент

Suggest (`staff_reply_suggest`) и клиентский `reply_to_free_text` — разные system/user промпты. Клиенту suggest напрямую не шлётся (admin UI).

## Почему ответы казались «слабее чата»

1. Мало структурированного состояния дела (только work_map CTA).
2. Нет явного списка «уже известно — не спрашивать».
3. Нет статуса документов pending/failed → риск говорить «получили / изучили».
4. Лимит turns и короткий REPLY → чаще шаблонный nudge.
5. Thinking/tools не используются как полноценный агент с доступом к содержимому файлов.

## Следующий фикс (этот PR)

ContextPack + усиление клиентского режима на существующем A→D. Без новых платежей и OCR.
