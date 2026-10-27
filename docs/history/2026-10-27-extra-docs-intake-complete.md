# 2026-10-27 — Завершение приёма доп. документов

## Цель

Клиент может прислать документ в любой момент (кабинет / чат MAX / почта);
сотрудник видит статусы; IMAP работает по timer без ручного запуска.

## Код

- Клиент: «Добавить документ» **над** картой дела + «Отправить по электронной почте».
- Чат MAX → `extra_unknown` + notify (реестр + статус Получен); классификатор не затирает extra_* в other.
- Unbound: байты вложений на диск; bind материализует файлы в дело.
- Dedup: `MailInboundProcessedStore`; письмо не processed при partial fail.
- systemd: `sfrfr-mail-inbound-docs.timer` (каждые 10 мин) + file lock в скрипте.
- Deploy: `vps_deploy.sh` включает timer, если IMAP не выключен явно.

## Живой прогон

См. `docs/acceptance/extra-docs-intake-live-2026-10-27.md`.

- SHA: `8c162565` (VPS = main)
- Timer `sfrfr-mail-inbound-docs.timer`: enabled, last success empty_inbox
- Пункты 1–7 ТЗ: **all_ok=true** на тестовом деле
