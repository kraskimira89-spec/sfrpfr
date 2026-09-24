# 2026-09-23 — Читаемые имена файлов и чистка папок SFRFR-cases

## Проблема

1. Зеркало добавляло к именам файлов префикс `uuid4().hex[:8]_`:
   на Диске лежало `df64c59a_Извещение_о_состоянии_ИЛС_….pdf`,
   а при отсутствии имени от MAX — `031f5639_document.bin`.
2. Накопились UUID-папки, дублирующие одноимённые ФИО-папки того же дела.
3. 19 legacy-папок: файлы лежат прямо в корне, без `incoming/` и `meta.txt`.
4. Не было способа посмотреть структуру Диска и почистить её из CLI.
5. UUID-папки не переименовывались в ФИО, даже когда имя клиента уже известно.

## Решение

- `disk._dedupe_remote_name` — читаемое имя со суффиксом при коллизии:
  `scan.pdf` → `scan_2.pdf`. Вместо hex-префикса.
- `disk._list_remote_names` — проверка коллизий в каталоге перед загрузкой.
- `disk.list_case_dir` / `move_case_path` / `delete_case_path` — служебные
  операции. `_cases_path_allowed(allow_root_files=True)` открывает корень
  папки дела только для них; обычные загрузки по-прежнему только в
  `incoming/` / `outgoing/` (+ `meta.txt`).
- `case_cleanup` — аудит и чистка:
  - `audit_case_folders` — UUID vs ФИО, legacy-корень, hex-префиксы;
  - `rename_uuid_folders_to_fio` — UUID → ФИО, если ФИО-папки ещё нет;
  - `migrate_uuid_into_fio` — уникальные файлы UUID→ФИО, затем удаление UUID;
  - `cleanup_duplicate_uuid_folders` — удаляет UUID-папку, если все её файлы
    уже есть в ФИО-папке; иначе оставляет;
  - `normalize_legacy_folders` — файлы из корня → `incoming/`, снятие
    префиксов, создание `meta.txt`.
- CLI (разрушительные — только с `--apply`):
  `yandex-disk-audit-folders`,
  `yandex-disk-rename-to-fio`,
  `yandex-disk-migrate-uuid`,
  `yandex-disk-cleanup-duplicates`,
  `yandex-disk-normalize-legacy`.

Порядок на prod: audit → normalize-legacy → rename-to-fio → migrate-uuid →
cleanup-duplicates (сначала dry-run, потом `--apply`).

## Находка про `outgoing/`

`outgoing/` пуст закономерно: маршрутизация `resolve_case_mirror_subfolder`
работает, но в БД по делам с загрузками нет ни одного документа типа
заявления (`client_signed_application` / `client_signed_appeal`).

## Проверено

`pytest tests/unit/test_case_cleanup.py tests/unit/test_case_mirror.py tests/unit/test_yandex_workspace.py`
— 25 passed. `ruff check` — clean.
