# 2026-09-24 — OCR source resolver Phase 1

- Реализован `resolve_ocr_bytes`: local → Disk(temp) → Storage fallback.
- YDB / VS Code plugin **не** в Phase 1; после пилота — опционально анонимные `ocr_job_metrics`.
- `INGEST_OCR_STORAGE_FALLBACK` default **True** на переход (jobs пока только Storage).

## Review fix (PR #37)

- Disk download errors: только `ok` / `error` / `status_code` (без path/detail/href).
- `local_path` только внутри `uploads_root()`.
- Warning при Storage fallback: `ocr_source_fallback=storage reason=no_verified_local_or_disk_source`.
- Документация: переходный режим + условие отключения после Phase 2 paths.
