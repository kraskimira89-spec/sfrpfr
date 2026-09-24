# 2026-09-24 — Учёт загрузок: MIME для document.bin + backfill documents

## Проблема

Аудит 133 дел: в `documents` почти пусто; local/Disk имеют единицы файлов.
Причины: клиенты редко шлют сканы; MAX часто даёт имя `document.bin`
(отсев по суффиксу); ранее silent-local без строки в БД.

## Цифры prod (2026-09-24)

| Метрика | Значение |
|---------|----------|
| cases | 133 |
| documents rows | 1 |
| clients | 137 (placeholder-имя ~37) |
| case_messages «Вложение не принято» | 5 |
| case_messages `[Документ]` | см. повторный прогон после фикса скрипта |

## Решение

- `align_filename_to_content` — `.bin`/кривое расширение → `.pdf/.jpg/.png` по magic.
- `upload_max_document` выравнивает имя до validate.
- CLI `documents-backfill-local` (`--apply`) — local uploads → documents + Storage.
- Идемпотентность: checksum или совпадение basename в `storage_path`.

## Проверено

`pytest tests/unit/test_file_security.py tests/unit/test_backfill_local_to_documents.py`
— 12 passed. `ruff` — clean.

На prod `--apply` backfill — отдельное подтверждение после merge/деплоя.
