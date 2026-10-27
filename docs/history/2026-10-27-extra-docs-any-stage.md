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

## Не в этом PR

Полный IMAP-cron в проде (модель `process_inbound_mail_message` готова к подключению).
Автопубликация входящих на Яндекс Диск — запрещена.
