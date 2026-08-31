# 2026-08-31 — Зеркало документов дела на Яндекс.Диск

## Политика

Источник истины документов: Supabase `pension-docs` (кабинет) / `storage/uploads/<case_id>/` (MAX).  
Яндекс.Диск — best-effort зеркало: `disk:/SFRFR-cases/{case_id}/` (UUID в пути).  
Ops без ПДн в путях: `disk:/SFRFR-ops` без изменений.

## Код

- `disk.py`: `CASES_FOLDER`, `ensure_case_folder`, `upload_case_file`, `mirror_case_document`
- `case_mirror.py`: `mirror_case_document_safe` (не ломает upload)
- Хуки: portal upload, MAX `_ingest_bytes`, legacy `/upload`
- CLI `yandex-disk-status` показывает `cases_folder`
- Docs: ТЗ-14, `yandex-workspace-setup.md`

Трекер: очередь SFRFR (продукт/infra).
