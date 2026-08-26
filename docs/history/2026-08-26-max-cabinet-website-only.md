# 2026-08-26 — Кабинет только на сайте; вложения в MAX принимаем

## Решение

1. Клиентский кабинет — **только сайт** (`CABINET_PUBLIC_URL`, `cabinet.proverkastaza.ru`). Mini-app не позиционировать как ЛК.
2. В чате MAX — подсказки, кнопки, «Позвать специалиста»; кнопка **«Кабинет на сайте»**.
3. Документы: **предпочтительно** кабинет на сайте (защищённо, после согласия). Если клиент прислал файл **в чат** — **принимаем** (не reject), подтверждаем, ставим задачу сотруднику (checklist / ops / amo `max_chat_docs`).
4. Канон copy: «предпочтительно кабинет на сайте; если отправили сюда — приняли, специалист увидит». Без абсолютного «в чат нельзя».

## Код / доки

- `src/sfrfr/integrations/max/intake.py`, `handler.py` (`UPLOAD_ACCEPTED_TEXT`, `_notify_staff_chat_docs`)
- `llm_chat.py`, `docs/MAX/prompt-agent-client-chat.md`
- ТЗ-09/20/23/24/26, strategy, AMO, architecture max-first, copy
- тесты: `test_max_intake.py` (accept в production), llm/login/channels

## Callbacks

Дерево `intake:…` / `svy:…` не ломали; `intake:device:max|web|help` сохранены, сменены подписи.
