# Аудит: OCR source = local + Яндекс.Диск (Ask, без кода)

**Дата:** 2026-09-24  
**Ветка:** `docs/tz13-ocr-sot-local-disk`  
**Канон:** [ТЗ-13 §3.7 / §16](../specs/13-document-ingest-v2.md), [ТЗ-13a](../specs/13a-document-ocr-coding-tz.md)  
**Скоуп:** только чтение репозитория. Код / миграции / systemd / VPS env **не менялись**.  
**ПДн:** без реальных client paths, ФИО, токенов.

---

## Вердикт

| Вопрос | Кратко |
|--------|--------|
| Соответствует ли as-is канону? | **Нет:** worker OCR читает только Supabase Storage |
| Local + Disk пишутся? | **Да** (best-effort), но пути **не** в `documents` |
| Download с Диска? | **Нет** API |
| `storage/processed/` | **Не используется** в репо; артефакты → Storage `ingest/` |

Следующий шаг после подтверждения: **Phase 1 source resolver** (без смены `INGEST_OCR_ENGINE`).

---

## 1. Как создаётся локальная копия в `storage/uploads`

**Функция:** `save_upload(case_id, filename, data)` → `src/sfrfr/storage/local.py`.

- Корень: `Settings.storage_local_path` (default `./storage/uploads`).
- Путь: `{root}/{case_id}/{8hex}_{safe_filename}`.
- **Не** `{case_id}/{document_id}/…` (это целевой вариант из paste; as-is — hex-префикс).

**Кто вызывает:**

| Путь | Поведение |
|------|-----------|
| `api/routes/documents.py` | сразу `save_upload` + `mirror_case_document_safe` |
| `case_mirror._persist_original_local` | внутри `mirror_case_document_safe(persist_local=True)` |
| CLI `cli/main.py` | ручная загрузка |
| Кабинет / MAX async ingest | `create_quarantine_document` → Storage + job; local/Disk через `_mirror_document_after_security` **после** успешного OCR (или сразу, если jobs недоступны) |

**Gap:** основной кабинетный/MAX поток сначала кладёт байты в Storage; local появляется при mirror, часто **после** OCR. `local_path` в БД не пишется.

---

## 2. Где SHA-256 вычисляется и хранится

| Место | Что |
|-------|-----|
| `document_ingest.sha256_hex` | `hashlib.sha256(data).hexdigest()` |
| `create_quarantine_document` | считает checksum → `documents.checksum_sha256` |
| `document_ingest_v2` / pipeline | дублирует в манифест `content_hash: sha256:…` |
| Дубликаты | `find_duplicate_checksum(case_id, checksum)` |

**Нет as-is:** `size_bytes`, `document_version` как колонки реестра (целевое §16 / Phase 2).

---

## 3. Как устроено зеркало на Яндекс.Диск

| Слой | Файл | Роль |
|------|------|------|
| Safe wrapper | `case_mirror.mirror_case_document_safe` | local (опционально) + Disk; bank_statement skip |
| Upload | `disk.mirror_case_document` → `upload_case_file` | `SFRFR-cases/{folder}/{incoming\|outgoing}/{remote}` |
| Folder | `format_case_disk_folder_name(fio, case_id)` | ФИО или UUID (ТЗ-14) |
| Backfill | `backfill_local_uploads.py`, `backfill_case_originals.py` | догон local → Disk |

Результат mirror (`local_path`, disk `path`/`remote_name`) **не persist** в `documents`.

OAuth / enable: `YANDEX_DISK_*` (secrets, не git). Публичные ссылки не создаются upload-путём.

---

## 4. Может ли worker скачать с Диска во temp (as-is)?

**Нет.** В `disk.py` есть upload (`upload_case_file`, `_put_upload`, ops/chat), **нет** `download_*`.

Для Phase 1 нужно добавить узкий download (bytes или temp) с policy `_cases_path_allowed`, без public link.

---

## 5. Как гарантировать удаление temp после OCR

As-is temp-flow для Disk **отсутствует**.

Целевой контракт (13a §4):

```text
resolved = resolve_ocr_bytes(...)
try:
    … OCR …
finally:
    if resolved.temp_path:
        resolved.temp_path.unlink(missing_ok=True)
```

Либо `resolve_ocr_bytes_ctx` contextmanager. Юнит-тест: файл отсутствует после выхода.

---

## 6. Где хранить `document_version`, `ocr_source_used`, review

| Поле | As-is | Куда (целевое) |
|------|-------|----------------|
| Review | `documents.ingest_review_required`, job `needs_review` | оставить |
| `checksum_sha256`, `storage_path`, ingest artifacts | есть | оставить |
| `document_version`, `local_path`, `yandex_disk_path`, `ocr_source_used`, `size_bytes`, statuses | **нет** | `documents` + audit на `document_ingest_jobs` (Phase 2) |
| `ocr_source_used` на run | нет | job row + `ingest.json` |

Статусы job as-is: `queued|running|completed|needs_review|failed` — не переименовывать в Phase 1.

---

## 7. Как стартует worker и откуда jobs

```text
systemd: docs/systemd/sfrfr-document-ingest.service
  ExecStart=…/python …/scripts/document_ingest_worker.py
    → run_worker(poll_seconds=settings.document_worker_poll_seconds)
      → process_next_document_ingest_job()
        → SELECT document_ingest_jobs WHERE status=queued …
        → process_document_ingest_job(id)
```

**Enqueue:** `create_quarantine_document` / admin rerun → `enqueue_document_ingest_job` → insert `document_ingest_jobs`.

**As-is bytes:** `storage.from_(pension-docs).download(documents.storage_path)` (~стр. 230–231 worker).

Celery/Redis — нет.

---

## 8. Точные файлы для реализации (будущий Phase 1)

| Путь | Действие |
|------|----------|
| `src/sfrfr/services/ocr_source_resolver.py` | **новый** |
| `src/sfrfr/services/document_ingest_worker.py` | resolve вместо голого Storage; finally temp |
| `src/sfrfr/integrations/yandex_workspace/disk.py` | **добавить** download |
| `tests/unit/test_ocr_source_resolver.py` | **новый** |
| расширить unit worker | mock порядка источников |

Phase 2+: миграция колонок, persist paths при mirror, опционально `documents_schema.py`.

**Не трогать в Phase 1:** systemd unit, `INGEST_OCR_ENGINE`, amoCRM, Celery.

---

## 9. Риски рассинхрона local vs Disk

1. **Порядок:** OCR из Storage до mirror → local/Disk могут появиться позже первого job.  
2. **Имена:** local `8hex_name` vs Disk deduped remote name — без `local_path`/`yandex_disk_path` в БД резолв хрупкий.  
3. **Best-effort mirror:** ошибка Disk не падает upload; local есть, Disk нет (или наоборот при backfill).  
4. **Hash mismatch:** правка/порча одного контура без другого.  
5. **Нет version:** re-upload создаёт новый document_id, но старые файлы в uploads остаются — риск взять чужой по имени.  
6. **Folder rename FIO:** смена ФИО клиента vs старый Disk path без обновления реестра.  
7. **Fallback Storage без флага (целевое):** нельзя молча читать Storage как primary — иначе снова «только bucket».

Митигация Phase 1–2: resolve по hash; path в БД; fail safe; Storage только по флагу.

---

## 10. Минимальный поэтапный план

Без смены роли Storage для кабинета и без amoCRM:

| Этап | Содержание | Код? |
|------|------------|------|
| **0** | Спека §16 + этот аудит | docs (этот PR) |
| **1** | Source resolver: local → Disk(temp) → Storage(флаг) → fail safe; Disk download; unit tests | после confirm |
| **2** | Колонки path/version/`ocr_source_used`/`size_bytes`; persist при upload/mirror | отдельно |
| **3+** | OCRAdapter / labor always-review / admin badges | отдельно |

Phase 1 **не** меняет Vision/Tesseract/text-layer и **не** переключает `INGEST_OCR_ENGINE`.

---

## Gaps спеки (закрыты в docs этого коммита)

| Было | Стало |
|------|-------|
| Storage как безусловный 3-й шаг OCR | только `*_OCR_FALLBACK=true`; MVP = local+Disk |
| Дополнение только в чате | §16 в ТЗ-13 + sync 13a |
| `storage/processed/` | зафиксировано: не используется |

**Код не менялся.** Проверено чтением: `local.py`, `case_mirror.py`, `disk.py`, `document_ingest_worker.py`, systemd unit, маршруты upload.
