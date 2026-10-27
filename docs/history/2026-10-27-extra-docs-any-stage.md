# 2026-10-27 — Доп. документы на любом этапе

## Поведение

- Клиент: постоянный блок «Добавить документ» + mailto с opaque `SFRFR-DOC`.
- Категории: дети / стаж / опекунство / договор / другое / не знаю → `extra_*`.
- Загрузка `extra_*` не сбрасывает pipeline / оплату / согласования; задача
  «Проверить новый документ» в чек-лист.
- Почта без токена → очередь `needs_binding` (не авто-привязка по ФИО/email).
- Staff: блок «Новые документы» + список unbound mail.

## API

- `GET /api/portal/cases/{id}/document-mail-hint`
- `POST .../documents` + `category`
- `GET /api/portal/admin/cases/{id}/extra-documents`
- `GET /api/portal/admin/mail-inbound/unbound`

Статусы review, bind unbound и IMAP-poll — см.
`docs/history/2026-10-27-extra-docs-review-status.md`.

## Не в этом PR

Автопубликация входящих на Яндекс Диск — запрещена.
