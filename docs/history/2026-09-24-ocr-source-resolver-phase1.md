# 2026-09-24 — OCR source resolver Phase 1

- Реализован `resolve_ocr_bytes`: local → Disk(temp) → Storage fallback.
- YDB / VS Code plugin **не** в Phase 1; после пилота — опционально анонимные `ocr_job_metrics`.
- `INGEST_OCR_STORAGE_FALLBACK` default **True** на переход (jobs пока только Storage).
