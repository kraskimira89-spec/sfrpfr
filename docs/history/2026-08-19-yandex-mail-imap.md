# IMAP read-only для proverkastaza@yandex.ru

**Дата:** 2026-08-19

## Код

- `src/sfrfr/integrations/yandex_workspace/mail_imap.py` — IMAP XOAUTH2, list/fetch, redact ПДн
- CLI: `yandex-mail-imap-ping`, `yandex-mail-list`, `yandex-mail-fetch`
- Admin API: `GET /admin/mail/inbox`, `GET /admin/mail/messages/{uid}?body=true`
- Флаг: `YANDEX_MAIL_IMAP_ENABLED` (default false)

## Онбординг

1. OAuth app `SFRFR Workspace` → scope `mail:imap_ro`
2. Почта → настройки → IMAP + OAuth-токены
3. Перевыпустить `YANDEX_OAUTH_ACCESS_TOKEN`
4. `.env`: `YANDEX_MAIL_IMAP_ENABLED=true`

## Ограничения

- Не автосоздавать дела из писем
- Тело — только по явному запросу, с depersonalize
- Вложения не скачиваем в Storage
