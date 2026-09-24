# План Phase 2 — реестр источников OCR (без кода)

**Дата:** 2026-09-24  
**Ветка:** `feature/ocr-source-registry-phase2`  
**База:** `main` @ `3c4dd75` (PR #37 Phase 1 merged)  
**Статус:** код в PR №38; **merge только после migration-first** — см. `2026-09-24-ocr-source-registry-phase2-rollout.md`

---

## Цель

Сохранять в реестре (`documents` + `document_ingest_jobs`) известные пути оригинала и фактический `ocr_source_used`, чтобы:

- не сканировать `uploads/{case_id}/` по hash (после заполнения `local_path`);
- брать Disk только по `yandex_disk_path` из БД;
- позже безопасно выключить `INGEST_OCR_STORAGE_FALLBACK`.

**Не входит:** отключение fallback, backfill боевых данных, OCR-движки, adapter, HITL labor, UI, YDB, Celery/Redis, systemd, amoCRM.

---

## 1. Где уже можно получить `local_path` / `yandex_disk_path`

| Источник | Как получить сейчас | Persist в БД? |
|----------|---------------------|---------------|
| `save_upload` → `Path` | `storage/local.py`: `{uploads}/{case_id}/{8hex}_{name}` | **Нет** |
| `mirror_case_document_safe` | возвращает `local_path` (abs), `path`/`remote_name` Disk при ok | **Нет** — caller игнорит |
| `disk.mirror_case_document` | `result["path"]` = `disk:/SFRFR-cases/{folder}/{sub}/{remote}` | только в return |
| `_mirror_document_after_security` | вызывает mirror, **результат отбрасывается** | Нет |
| `create_quarantine_document` | пишет Storage + `checksum_sha256`; **не** local/Disk до job | Нет paths |
| Legacy `documents.py` / CLI | `save_upload` + mirror сразу | Нет в `documents` |
| Sync `document_upload.py` | mirror после insert; result не пишется | Нет |

**Вывод:** пути уже возникают в runtime mirror/save; Phase 2 = **прокинуть return → UPDATE `documents`**.

---

## 2. Upload / mirror-пути, которые нужно затронуть

### Обязательные (production OCR)

1. **`create_quarantine_document`** (`document_ingest_worker.py`)  
   - При insert: `size_bytes=len(data)`, `document_version=1`, `primary_ocr_source` пока `none` или оставить null до local.  
   - **Ранний local (рекомендация плана):** сразу после успешного Storage upload вызвать `save_upload` (или `_persist_original_local`) и записать **относительный** `local_path` + `primary_ocr_source=local_storage` при hash match.  
   - Иначе первый job по-прежнему уйдёт в Storage fallback (порядок mirror сейчас **после** OCR).

2. **`_mirror_document_after_security`**  
   - Принять `document_id`.  
   - После `mirror_case_document_safe`: UPDATE `yandex_disk_path` из `result["path"]` (только если `ok`); UPDATE `local_path` если ещё пуст и есть local.  
   - Не затирать валидный `yandex_disk_path` при ошибке mirror.

3. **`process_document_ingest_job`**  
   - После успешного `resolve_ocr_bytes_ctx`: UPDATE documents (`ocr_source_used`, `ocr_source_verified_at`) и job (`ocr_source_used`, `bytes_sha256`, `resolve_trace`).  
   - При `OcrSourceUnresolved`: job `resolve_trace` = безопасные коды; `ocr_source_used` не ставить ложным (или `none` только если колонка уже есть и политика так решена — предпочтительно **не писать** / null).

### Желательные (консистентность, не блокируют Phase 2 MVP)

4. **`api/routes/documents.py`** — legacy upload: после save+mirror обновить row, если document_id известен (часто нет quarantine-документа — уточнить: может только local без documents; тогда skip).  
5. **`document_upload.py`** (sync ingest) — после mirror persist paths.  
6. **CLI `sfrfr upload`** — аналогично, если создаётся documents row.

**Не трогать в Phase 2:** backfill CLI (`yandex_disk-backfill-*`) — отдельная задача.

---

## 3. Относительный `local_path` (не abs VPS)

Канон записи:

```text
{case_id}/{8hex}_{safe_name}
```

относительно `Settings.storage_local_path` / `uploads_root()`.

Хелпер (будущий код):

```text
rel = path.resolve().relative_to(uploads_root().resolve())
# store str(rel) with forward slashes
```

В resolver Phase 1 уже читает:

- `document.local_path` как Path — нужно принимать **и** relative (join с `uploads_root()`), и legacy abs внутри root (sandbox Phase 1).

План: одна функция `normalize_local_path_for_db(path) -> str` + `resolve_local_path_from_db(stored) -> Path`.

---

## 4. Одна SQL-миграция

Формат имени (как в репо): `YYYYMMDDHHMMSS_…sql`  
Предложение: `supabase/migrations/20260924120000_ocr_source_registry_phase2.sql`

Содержание (черновик):

- `documents`: `size_bytes`, `document_version NOT NULL DEFAULT 1`, `local_path`, `yandex_disk_path`, `primary_ocr_source`, `ocr_source_used`, `ocr_source_verified_at` — все nullable кроме version default.  
- `document_ingest_jobs`: `ocr_source_used`, `bytes_sha256`, `resolve_trace jsonb`.  
- Опционально CHECK на enum-значения *или* валидация в приложении (предпочтительно app-level, как многие text-поля ingest).  
- Без NOT NULL на path-полях (старые rows).  
- Без RLS-изменений (наследуют существующие).

`documents_schema.insert_document_row` / updates: расширить payload; если колонок нет на старом стенде — graceful (как сейчас для ingest columns) **или** полагаться что миграция применена вместе с деплоем.

---

## 5. `source_used` / `bytes_sha256` после resolver

В `process_document_ingest_job` внутри `with resolve_ocr_bytes_ctx(...)`:

После успешного resolve (до или сразу после antivirus OK — **после** успешного resolve bytes, даже если antivirus blocked — лучше писать source только если байты реально пошли в ingest; если infected — source_used всё же полезен для аудита «откуда читали»):

Рекомендация плана: писать audit **после успешного resolve**, до OCR:

- `bytes_sha256 = resolved.sha256`  
- `ocr_source_used = resolved.source_used` на job + documents  
- `ocr_source_verified_at = now()` на documents  

При fail antivirus — поля уже показывают, что файл брали из local/disk/storage.

Экспортировать из resolver безопасный `trace` (сейчас только в exception). Для успеха: расширить `ResolvedBytes` опциональным `resolve_trace: list[str]` **или** собирать в worker минимальный `["ok"]` / не писать trace на success. ТЗ просит trace попыток — лучше resolver всегда возвращает `trace` (коды веток), без путей.

---

## 6. Безопасный `resolve_trace`

Allowlist кодов (как в ТЗ + Phase 1):

```text
local_path_outside_uploads_root
local_path_miss_or_hash_mismatch
local_scan_no_hash_match
local_scan_skipped_no_hash
yandex_disk_path_absent
yandex_disk_hash_or_size_mismatch
yandex_disk_error:<ExceptionName>   # только type name
yandex_disk_download_failed
supabase_storage_fallback_disabled
supabase_storage_path_absent
supabase_storage_hash_or_size_mismatch
supabase_storage_error:<ExceptionName>
```

Фильтр перед записью в jsonb: отбросить строки с `/`, `\`, `disk:`, `@`, пробелами ФИО-паттернов; max N элементов; без hash/SHA.

Логи: только `ocr_source_used=…` и job_id/case_id truncated — **без** local/disk path (уже почти так).

---

## 7. Точные файлы изменений (после confirm)

| Файл | Действие |
|------|----------|
| `supabase/migrations/20260924120000_ocr_source_registry_phase2.sql` | **новый** |
| `src/sfrfr/services/document_ingest_worker.py` | size/version на create; early local; mirror persist; audit после resolve |
| `src/sfrfr/integrations/yandex_workspace/case_mirror.py` | опционально: возвращать relative local; не логировать full Disk path |
| `src/sfrfr/storage/local.py` | хелперы relative path |
| `src/sfrfr/services/ocr_source_resolver.py` | resolve relative local_path; вернуть `trace` на success |
| `src/sfrfr/services/documents_schema.py` | при необходимости allow-list новых колонок в update helpers |
| `src/sfrfr/services/document_upload.py` | persist после mirror (sync path) |
| `tests/unit/test_ocr_source_registry_phase2.py` | **новый** |
| `docs/specs/13a-document-ocr-coding-tz.md` | Phase 2 done checklist |
| `docs/history/2026-09-24-ocr-source-registry-phase2-plan.md` | этот план |

**Не менять:** Vision/Tesseract/`INGEST_OCR_ENGINE`, systemd, queue semantics, amo, YDB, default fallback True.

---

## 8. План unit-тестов (mocks)

1. `create_quarantine` insert содержит `size_bytes` + relative `local_path` (mock save_upload).  
2. Mirror ok → UPDATE получает `yandex_disk_path` без ФИО в логах (assert mock update payload).  
3. Mirror fail → существующий `yandex_disk_path` не затирается.  
4. После resolve → job `ocr_source_used` + `bytes_sha256` + safe trace.  
5. Unresolved → нет ложного `ocr_source_used=local_storage`.  
6. Relative `local_path` резолвится внутри uploads_root; abs outside — rejected (уже есть тест Phase 1).  
7. `resolve_trace` filter strips path-like strings.  

Без сети Disk/Storage/Vision.

---

## 9. Подтверждения границ

| Тема | Phase 2 |
|------|---------|
| Storage fallback default / env | **Не отключаем** |
| OCR engines / `INGEST_OCR_ENGINE` | **Не трогаем** |
| Queue / systemd / poll | **Не трогаем** |
| amoCRM / YDB / Celery / Redis | **Не трогаем** |
| Массовый backfill / VPS `FALLBACK=false` | **Отдельные задачи после Phase 2** |
| Пути с ФИО в audit/logs | **Запрещено** (в БД `yandex_disk_path` хранит ops-path с ФИО-folder — это реестр expert+; в logs/trace — нет) |

**Замечание по ПДн:** колонка `yandex_disk_path` в `documents` неизбежно содержит сегмент ФИО при layout ТЗ-14. Это **закрытый реестр**, не публичный log. Trace/логи — только коды.

---

## Рекомендуемый порядок реализации (после «да»)

1. Миграция SQL.  
2. Хелперы relative local path.  
3. Запись при create + early local.  
4. Persist после mirror.  
5. Audit после resolver (+ trace на ResolvedBytes).  
6. Тесты + docs.  
7. PR (отдельный от отключения fallback).

---

## Риски, если early local не сделать

Если только писать paths после `_mirror_document_after_security` (после OCR), **первый** job новых cabinet/MAX загрузок по-прежнему пойдёт в Storage fallback → Phase 2 не приблизит продуктовую модель. Поэтому early `save_upload` + `local_path` в `create_quarantine_document` — **ключевой** пункт плана.
