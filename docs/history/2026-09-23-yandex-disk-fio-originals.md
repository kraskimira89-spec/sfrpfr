# 2026-09-23 — Оригиналы в папке дела по ФИО (local + Яндекс.Диск)

## Цель

Upload (MAX / кабинет) → байт-в-байт оригинал в `storage/uploads/{case_id}/`
и тот же объект на Яндекс.Диске в `disk:/SFRFR-cases/{Фамилия Имя Отчество}/incoming|outgoing/`.

## Решение

- Имя папки: `format_case_disk_folder_name` (`person_name` → «Фамилия Имя Отчество»;
  fallback UUID). Без телефона/СНИЛС в пути.
- `mirror_case_document_safe`: local `save_upload` + Disk с `folder_name`.
- Layout `incoming/outgoing/chat` + `meta.txt` (case_id) сохранён.
- Primary по-прежнему Supabase `pension-docs`; Диск — best-effort.

## Проверено

`pytest tests/unit/test_case_original_mirror.py tests/unit/test_case_mirror.py
tests/unit/test_yandex_workspace.py tests/unit/test_create_quarantine_disk_mirror.py`

## Ручное

- Обновить формулировку в `docs/contracts/pdn-policy.md` («только идентификатор дела»
  → допускается ФИО в пути служебного зеркала).
- Миграция уже существующих UUID-папок на Диске (backfill / rename).
