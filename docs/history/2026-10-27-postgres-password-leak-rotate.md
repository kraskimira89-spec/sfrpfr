# 2026-10-27 — раскрытие пароля Postgres и ротация

- В журнале агента Cursor попал connection string с **действующим** паролем → пароль считать скомпрометированным.
- Значение в history/PR/чат **не** публикуется.
- Сгенерирован новый секрет: локальный файл `secrets/postgres-password-rotated.env` (gitignored).
- App VM B: `ALTER ROLE` от пользователя `DATABASE_URL` → `InsufficientPrivilege` (нужен суперuser на VM C).
- SSH на VM C (`51.250.13.240`) с рабочей станции — timeout (allowlist).
- Канон выполнения: [docs/ops/tz-yandex-assistant-rotate-postgres-password.md](../ops/tz-yandex-assistant-rotate-postgres-password.md).
- Локальный `.env` возвращён к рабочему (ещё старому) паролю до завершения ротации на VM C + обновления VPS `.env`.
