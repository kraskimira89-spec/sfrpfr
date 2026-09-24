# 2026-09-24 — Папка на Диске сразу по ФИО из MAX / заявки

## Проблема

ФИО из профиля MAX или заявки с сайта попадало в `clients.full_name`,
но папка `SFRFR-cases/` оставалась UUID, пока не запускали ручной
`yandex-disk-rename-to-fio`.

## Решение

- `sync_case_disk_folder_name_safe` — rename UUID→ФИО / создать layout / снять дубль.
- `sync_client_cases_disk_folders_safe` — то же для всех дел клиента.
- Хуки: `apply_max_display_name` (MAX), `public_leads` (сайт),
  `create_case_for_client` / `create_my_case` (кабинет), перед зеркалом файла.
- Заглушки `MAX 123` не становятся именем папки.

## Проверено

`pytest tests/unit/test_case_mirror.py …` — 28 passed.
