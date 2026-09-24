# Rollout / rollback — OCR Phase 2 (PR №38)

**PR:** [#38](https://github.com/kraskimira89-spec/sfrpfr/pull/38)  
**Ветка:** `feature/ocr-source-registry-phase2`  
**Миграция:** `supabase/migrations/20260924120000_ocr_source_registry_phase2.sql`  
**Статус:** migration-first обязателен; merge в `main` только после отчёта о staging + production migration.

Код PR пишет новые колонки реестра OCR. `insert` / `update` **не** graceful к отсутствующим полям → деплой до migration даст PostgREST «column does not exist».

---

## Rollout

1. Apply additive migration in **staging**.
2. Deploy PR #38 code to **staging**.
3. Smoke-test one non-production PDF/image upload:
   - document row, ingest job, `ocr_source_used`, `bytes_sha256` / checksum,
   - sanitized `resolve_trace`, `local_status`.
4. Verify no PostgREST «column does not exist» errors.
5. Apply the **same** migration in **production**.
6. Only after successful production migration: squash-merge PR #38 and allow deployment.
7. Production smoke: один безопасный тестовый файл; наблюдение worker 30–60 мин.

Зависимость:

```text
migration применена → код слит и развёрнут → smoke upload → наблюдение
```

Не наоборот.

## Rollback

- Roll back **application code** to the prior release if ingestion errors occur.
- Do **not** drop Phase 2 columns during incident rollback: migration is additive; old code tolerates extra columns.
- Keep `INGEST_OCR_STORAGE_FALLBACK=true`.
- Capture `job_id`, `document_id` and error **type**; do not log paths, names, raw tokens, content or personal data.

## Stop conditions (откат кода, не схемы)

- PostgREST: неизвестная колонка / неверный запрос.
- Рост неуспешных upload / ingest jobs.
- Утечка abs path, `disk:/…`, URL или имени файла в публичный лог/аналитику.
- `local_status=verified` при `ocr_source_used` ∈ {`yandex_disk`, `supabase_storage`}.
- Отключение или изменение поведения `INGEST_OCR_STORAGE_FALLBACK`.

## Проверка схемы после migration (без клиентского файла)

- `documents`: новые колонки существуют; path/status/source — nullable; `document_version NOT NULL DEFAULT 1`.
- `document_ingest_jobs`: `ocr_source_used`, `bytes_sha256`, `resolve_trace`.
- Нет backfill строк; RLS не менялся.

## Smoke checklist (staging / prod)

| Проверка | Ожидание |
|----------|----------|
| Upload без 400/500 PostgREST | ok |
| Ранняя quarantine local-копия до job | ok |
| Job: `ocr_source_used` заполнен | ok |
| `resolve_trace` | только allowlist-коды |
| Disk/Storage fallback | `local_status` ≠ `verified` |
| Fallback flag | `true` |

Результаты smoke фиксировать комментарием в PR: время, окружение, усечённый `job_id`/`document_id`, фактический `ocr_source_used`, статус, отсутствие ошибок.
