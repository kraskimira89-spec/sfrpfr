# 2026-09-09 — Дубли start_dialog / приветствия в чате сотрудника

## Симптом

В ленте дела (пример ПС-26-ИН-499714) три раза подряд:
«Нажал кнопку: start_dialog» + то же приветствие «Здравствуйте, Инна!…».

## Причина

1. Дедуп webhook работал только для текстовых сообщений (`message_id`), **callback игнорировался**.
2. Повторное «Начать» / ретрай MAX снова вызывал `_handle_bot_start` и `_send_welcome_sequence` без проверки, что приветствие уже ушло.
3. Каждое нажатие писалось в `case_messages` без `external_message_id`.

## Исправление

- `claim_callback_id` — повтор того же `callback_id` → `duplicate_callback` (ACK всё равно шлём).
- `MaxIntakeStore.claim_welcome` + поле `welcome_sent_at` — приветствие один раз на intake.
- Кнопка в ленту с `external_message_id=max_cb:{callback_id}`.

## Критерий

Повторный webhook/клик «Начать» не добавляет второе полное приветствие в MAX и в кабинет.
