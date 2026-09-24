# ТЗ-13a: Coding — OCR source resolver и адаптер (поверх ТЗ-13)

**Статус:** coding-ready (документация для реализации; код в этом PR не менять)  
**Канон продукта/архитектуры:** [13-document-ingest-v2.md](13-document-ingest-v2.md) (§3.7, §15), [14-yandex-workspace.md](14-yandex-workspace.md)  
**Ветка фиксации SoT:** `docs/tz13-ocr-sot-local-disk`  
**Аудитория:** coding-агент / разработчик. Без «разобраться» — только контракты, пути файлов, критерии приёмки.

> **Важно:** этот документ **не** вводит второй SoT. Primary байты OCR = local + Яндекс.Диск; Supabase Storage `pension-docs` = кабинет / quarantine / verified / signed URL / артефакты / backup. OCR-read из Storage — **только** при `SUPABASE_STORAGE_OCR_FALLBACK` / `INGEST_OCR_STORAGE_FALLBACK=true` (не обязателен для MVP ТЗ-13). Канон дополнения: [13-document-ingest-v2.md](13-document-ingest-v2.md) §16. Не следовать paste «только Supabase».

---

## 1. Цель / out of scope

### 1.1. Цель

Сделать так, чтобы существующий async worker читал **байты оригинала** для OCR в порядке:

```text
1) VPS storage/uploads/{case_id}/…   (size + sha256 + version vs реестр)
2) Яндекс.Диск по yandex_disk_path → temp → finally delete
3) Supabase Storage pension-docs — ТОЛЬКО если fallback-флаг = true
4) иначе OcrSourceUnresolved (fail safe)
```

и чтобы OCR шёл через **единый интерфейс `OCRAdapter`** (Phase 3+) поверх уже существующих движков (text-layer → Yandex Vision → Tesseract), без новой очереди и без смены executor. **Phase 1 не трогает** `INGEST_OCR_ENGINE`.

### 1.2. Out of scope (запрещено вносить в рамках этого ТЗ)

| Тема | Почему нет |
|------|------------|
| Celery / Redis / новая очередь / RQ / Temporal | Executor уже есть: `scripts/document_ingest_worker.py` + systemd |
| Замена SoT на «только Supabase Storage» | Противоречит ТЗ-13 §3.7 / §15 |
| GPT-vision / LLM как OCR | ТЗ-13: LLM только classify/extract/draft после текста |
| amoCRM (интеграция, поля, выгрузки OCR) | amo выключена; ПДн/OCR туда не пишем |
| YDB / плагин YDB VS Code для OCR | Отдельный контур; см. §13 |
| Поиск файлов на Диске по ФИО «вслепую» | DB = SoT путей; Disk = архив по известному path |
| Публичные ссылки Диска | Запрещено |
| Переименование папок Диска с ФИО → case_id | Сохраняем layout ТЗ-14 as-is |
| Полный rewrite `extract_text` / удаление Tesseract | Обратная совместимость CLI/тестов |

---

## 2. As-is vs to-be (по реальному коду)

### 2.1. Executor (оставить)

| Компонент | Путь | Поведение as-is |
|-----------|------|-----------------|
| CLI entry | `scripts/document_ingest_worker.py` | `run_worker(once=…, poll_seconds=settings.document_worker_poll_seconds)` |
| Логика | `src/sfrfr/services/document_ingest_worker.py` | `create_quarantine_document` → `enqueue_document_ingest_job` → `process_document_ingest_job` / `process_next_document_ingest_job` / `run_worker` |
| systemd | `docs/systemd/sfrfr-document-ingest.service` | `ExecStart=…/python …/scripts/document_ingest_worker.py` |

**To-be:** тот же процесс; меняется только способ получения `data: bytes` внутри `process_document_ingest_job`.

### 2.2. Критический gap: источник байтов

**As-is** (`process_document_ingest_job`, ~стр. 230–231):

```python
source_path = str(row.get("storage_path") or "")
data = client.storage.from_(PRIVATE_STORAGE_BUCKET).download(source_path)
```

- Единственный вход OCR — Supabase Storage `pension-docs`.
- Local и Disk уже пишутся при upload/mirror, но **worker их не читает**.

**To-be:** вызов `resolve_ocr_bytes(document_row) → ResolvedBytes` **до** antivirus/OCR; Storage — только при флаге; иначе fail safe.

### 2.3. Запись оригиналов (уже есть, но метаданные не в БД)

| Функция | Файл | Что делает | Gap |
|---------|------|------------|-----|
| `save_upload(case_id, filename, data)` | `src/sfrfr/storage/local.py` | `storage/uploads/{case_id}/{8hex}_{safe_name}` | путь **не** пишется в `documents` |
| `mirror_case_document_safe(…)` | `src/sfrfr/integrations/yandex_workspace/case_mirror.py` | local (`persist_local=True`) + Disk; возвращает `local_path`, `path` (disk), `folder_name` | результат **не** сохраняется в row документа |
| `mirror_case_document(…)` | `src/sfrfr/integrations/yandex_workspace/disk.py` | upload в `SFRFR-cases/{folder}/{incoming\|outgoing}/{remote}` | **нет** `download_*` API |
| `_mirror_document_after_security` | `document_ingest_worker.py` | best-effort после успешного ingest (или сразу, если нет jobs) | зеркало **после** OCR из Storage — порядок обратный целевому |

**To-be Phase 1:** resolver читает то, что уже лежит; плюс сохранение `local_path` / `yandex_disk_path` при upload/mirror (минимальная запись в БД — Phase 2, если Phase 1 резолвит по hash/имени без колонок).

### 2.4. OCR движки (уже частично v2)

| Слой | Файл | As-is | Gap |
|------|------|-------|-----|
| Facade CLI | `src/sfrfr/ocr/engine.py` | `extract_text` / `extract_texts` / `extract_text_from_bytes`; PDF text→raster+Tesseract; **нет Vision** | нет adapter, нет confidence/coords |
| Ingest v2 | `src/sfrfr/services/document_ingest_v2.py` | `run_document_ingest_v2` → `_extract_pages` → text_layer / `_ocr_image` (Vision→Tesseract по `INGEST_OCR_ENGINE`) | нет единого `OCRAdapter`; Vision/Tesseract — private; confidence/bbox нет |
| Placement/quality | `src/sfrfr/services/document_ingest.py` | `run_ingest_pipeline`, labor drafts | трудовая **не** всегда `manual_review_required` |

**To-be Phase 3:** тонкая обёртка `OCRAdapter` над существующими `_vision_ocr` / `_tesseract_ocr` / text_layer; `engine.py` остаётся facade.

### 2.5. Очередь / модель job

Миграция `supabase/migrations/20260901170000_document_ingest_v2_async.sql`:

Таблица `document_ingest_jobs`:

| Колонка | Есть |
|---------|------|
| `id`, `case_id`, `document_id`, `job_type` | да |
| `status` (`queued\|running\|completed\|needs_review\|failed`) | да |
| `attempts`, `max_attempts`, `progress_percent`, `current_stage`, `last_error` | да |
| `locked_by`, `locked_at`, `available_at` | да |
| `ocr_source_used`, `primary_ocr_source`, audit path fields | **нет** |

`documents` (customer journey + ingest v2 migrations): есть `checksum_sha256`, `storage_path`, `ingest_status`, `ingest_review_required`, `ingest_artifact_path`, `ingest_manifest_path`, `ingest_engine`, `quality_report` и т.д.

**Нет колонок:** `local_path`, `yandex_disk_path`, `document_version`, `primary_ocr_source`, `ocr_source_used`.

### 2.6. Employment book as-is

В `run_ingest_pipeline` / labor ветке: `labor_book|labor|workbook` → drafts в `labor_timeline_drafts`, статус часто `under_review` / quality-driven — **не** жёсткий always-`ingest_review_required=true`.

**To-be Phase 4:** любые трудовые → `ingest_review_required=true` (+ status совместимый с admin queue), classify/LLM extract **не** считать verified без эксперта.

### 2.7. Admin HITL as-is

`src/sfrfr/api/routes/admin_portal.py`: `list_ingest_review_documents`, accept/rerun/reject (ingest review). Превью через Storage signed URL.

**Gap Phase 5:** явные бейджи `ocr_source_used` / page sources; split-view по артефактам; не блочить Phase 1.

---

## 3. Target data model

### 3.1. `documents` — целевые поля (добавлять миграцией в Phase 2, если ещё нет)

| Поле | Тип | Смысл |
|------|-----|--------|
| `checksum_sha256` | text | уже есть; канон hash содержимого (= `sha256` в §16) |
| `size_bytes` | bigint null | целевое; as-is может отсутствовать — Phase 2; до колонки сверять len(data) после чтения |
| `document_version` | int not null default 1 | инкремент при re-upload / rerun OCR с новым артефактом |
| `local_path` | text null | абсолютный или относительный к `storage_local_path` путь VPS |
| `local_status` | text null | опционально: `present` \| `missing` \| `corrupt` \| … |
| `yandex_disk_path` | text null | полный путь API, напр. `disk:/SFRFR-cases/…/incoming/ils.pdf` |
| `yandex_disk_status` | text null | опционально |
| `storage_path` | text | уже есть; quarantine/verified в `pension-docs` (= `supabase_storage_path`) |
| `primary_ocr_source` | text null | ожидаемый primary при enqueue |
| `ocr_source_used` | text null | фактический источник байтов последнего успешного resolve (**один** на job run) |
| `ocr_source_verified_at` | timestamptz null | когда hash/source подтверждены |
| `ingest_status` | text | as-is enum-строки |
| `ingest_review_required` | bool | as-is |

Допустимые значения `*_ocr_source*` (канон §16; алиасы в скобках):

```text
local_storage (local) | yandex_disk | supabase_storage (storage) | none
```

### 3.2. `document_ingest_jobs` — audit (Phase 2)

| Поле | Тип | Смысл |
|------|-----|--------|
| `ocr_source_used` | text null | откуда взяли байты в этом run |
| `bytes_sha256` | text null | hash фактически прочитанных байтов (сверка) |
| `resolve_trace` | jsonb null | опционально: `[{source, ok, reason}]` без ПДн/путей с ФИО в логах приложения — в jsonb path можно, в Tracker/Wiki/Git — нельзя |

Статусы job **не менять** enum без необходимости: `queued|running|completed|needs_review|failed`.

### 3.3. Артефакты (уже в v2)

`ingest.json` / `extracted.md` — схема ТЗ-13 §7; дополнить (Phase 3+):

```json
{
  "ocr_source_used": "local",
  "document_version": 1,
  "content_hash": "sha256:…",
  "pages": [{ "page": 1, "source": "text_layer", "confidence": null, "bbox": null }]
}
```

`confidence` / `bbox` — nullable; заполнять только если движок отдаёт (Vision blocks — по возможности; Tesseract — опционально позже).

---

## 4. Source resolver contract (Phase 1 — главный deliverable)

### 4.1. Модуль

Новый файл (предпочтительно):

```text
src/sfrfr/services/ocr_source_resolver.py
```

Публичный API (имена фиксируем):

```text
resolve_ocr_bytes(document: dict, *, case_id: str) -> ResolvedBytes
```

```text
@dataclass
class ResolvedBytes:
    data: bytes
    sha256: str
    size_bytes: int
    source_used: Literal["local_storage", "yandex_disk", "supabase_storage"]
    # алиасы local/storage допустимы при записи в БД — нормализовать к канону §16
    local_path: str | None
    yandex_disk_path: str | None
    storage_path: str | None
    document_version: int | None
    temp_path: Path | None   # если скачали с Диска во временный файл
```

Ошибки: свой exception `OcrSourceUnresolved` (или аналог) с `trace` без текста документа.

### 4.2. Алгоритм (псевдокод)

```text
expected_hash = document.checksum_sha256
expected_size = document.size_bytes   # если колонки нет — skip size check
expected_ver  = document.document_version  # если нет — считать 1 / skip

1. LOCAL
   candidates =
     - document.local_path если задан и файл существует
     - иначе scan storage/uploads/{case_id}/:
         * sha256 файла == expected_hash
         * (не брать только по имени)
   if found:
     data = read_bytes
     if expected_size and len(data) != expected_size → skip
     if expected_hash and sha256(data) != expected_hash → skip
     # version: если в meta файла/имени нет — доверять row.document_version
     return ResolvedBytes(source_used="local_storage", …)

2. YANDEX_DISK
   path = document.yandex_disk_path
   if not path:
     # НЕ искать по ФИО. Только известный path / segment+name из meta (Phase 2).
     # Без meta → skip Disk.
   download to tempfile (suffix по имени)
   try:
     data = read temp
     if expected_size and len(data) != expected_size → fail this branch
     if expected_hash and sha256(data) != expected_hash → fail this branch
     return ResolvedBytes(source_used="yandex_disk", temp_path=…)
   finally:
     # вызывающий ОБЯЗАН удалить temp в finally; resolver может
     # предоставить contextmanager resolve_ocr_bytes_ctx(...)

3. STORAGE FALLBACK — только если
   SUPABASE_STORAGE_OCR_FALLBACK или INGEST_OCR_STORAGE_FALLBACK == true
   if flag and document.storage_path:
     data = supabase.storage.download(storage_path)
     verify size/hash if expected
     return source_used="supabase_storage"

4. FAIL SAFE
   raise OcrSourceUnresolved — job → needs_review / retry per existing policy
   НЕ вызывать OCR; НЕ молча падать на Storage без флага
```

### 4.3. Download с Диска (нужен для Phase 1 Disk-ветки)

Сейчас в `disk.py` **нет** download. Добавить узкую функцию, например:

```text
download_case_file(path: str) -> bytes
# или download_to_temp(path) -> Path
```

Требования:

- OAuth headers как у upload;
- путь только внутри `SFRFR-cases/…` (reuse `_cases_path_allowed` / policy);
- **не** создавать public link;
- temp файл удалять в `finally` у worker.

### 4.4. Встраивание в worker (Phase 1)

В `process_document_ingest_job` **заменить** прямой `storage.download` на:

```text
resolved = resolve_ocr_bytes(row, case_id=…)
try:
    data = resolved.data
    # antivirus + run_document_ingest_v2 как сейчас
    # после успеха: обновить ocr_source_used (если колонка есть — Phase 2)
finally:
    if resolved.temp_path: resolved.temp_path.unlink(missing_ok=True)
```

**Phase 1 не меняет** порядок движков OCR внутри `run_document_ingest_v2`.

### 4.5. Приёмка Phase 1

- [ ] При наличии local файла с тем же sha256(+size) worker **не** вызывает Storage download (unit mock).
- [ ] При отсутствии local и наличии `yandex_disk_path` — temp download + delete в finally (mock Disk).
- [ ] При `INGEST_OCR_STORAGE_FALLBACK=false` (или unset=false для MVP) и без local/Disk — `OcrSourceUnresolved`, **не** Storage.
- [ ] При флаге fallback true и отсутствии local/Disk — Storage как as-is.
- [ ] Hash/size mismatch → не использовать файл, следующая ветка / fail.
- [ ] Один `ocr_source_used` на job run (когда колонка есть — Phase 2; в Phase 1 — хотя бы в возврате ResolvedBytes / лог без ПДн).
- [ ] Нет Celery/новой очереди; systemd unit без изменений по смыслу; `INGEST_OCR_ENGINE` не трогать.
- [ ] Нет поиска по ФИО: unit-тест, что resolver не вызывает `lookup_case_client_full_name` для resolve.

---

## 5. OCRAdapter contract (Phase 3)

### 5.1. Интерфейс

Новый модуль (предпочтительно):

```text
src/sfrfr/ocr/adapter.py
```

```text
class OCRAdapter(Protocol):
    def extract_page(
        self,
        image_or_pdf_page: bytes,
        *,
        mime: str,
        page_index: int,
        engine_pref: str,  # auto|vision|tesseract|text_layer
    ) -> OCRPageResult: ...

@dataclass
class OCRPageResult:
    text: str
    source: str          # text_layer|ocr_vision|ocr_tesseract|failed|plain_file
    engine: str | None
    confidence: float | None   # 0..1 или среднее; null если неизвестно
    boxes: list[dict] | None   # [{text,x,y,w,h}] опционально
    error: str | None
```

### 5.2. Mapping на существующий код

| Adapter path | Реализация as-is |
|--------------|------------------|
| text_layer PDF | `_extract_pdf_pages` ветка pypdf в `document_ingest_v2.py` |
| vision | `_vision_ocr` / `_vision_configured` |
| tesseract | `_tesseract_ocr` / `engine._ocr_pil` |
| plain txt/md | `engine.extract_text` suffixes |
| primary + future fallback | `INGEST_OCR_ENGINE=auto` + `INGEST_VISION_FALLBACK_TESSERACT` |

Phase 3 = **thin wrap**: перенести вызовы под adapter без смены порогов `INGEST_MIN_CHARS_*`.

`sfrfr.ocr.engine.extract_text` — оставить публичным; внутри может делегировать в adapter позже (не обязательно в Phase 3).

---

## 6. Pipeline end-to-end (целевой)

```text
cabinet / MAX upload
  → validate_file_bytes
  → create_quarantine_document:
        upload → pension-docs/quarantine/…
        insert documents (checksum_sha256, storage_path, …)
        enqueue document_ingest_jobs (status=queued)
  → best-effort (желательно до или в job):
        save_upload + mirror_case_document_safe
        записать local_path / yandex_disk_path (Phase 2)
  → systemd worker: process_next_document_ingest_job
        resolve_ocr_bytes: local → Disk(temp) → Storage(только флаг)
        antivirus
        run_document_ingest_v2 (engines)  # Phase 1: без смены INGEST_OCR_ENGINE
        quality gate / employment policy
        artifacts → pension-docs/ingest/…   # не storage/processed/
        verified copy в Storage (кабинет)
        job completed | needs_review
        зафиксировать ocr_source_used (Phase 2 колонка)
  → expert HITL (admin ingest-review) при ingest_review_required
  → только после verified / accept:
        classify / extract / audit_ils / draft (LLM)
```

Правила:

- DB = SoT статусов и путей;
- Disk = архив файлов, **не** poller папок;
- AI/LLM не на quarantine и не на `needs_ingest_review` без явного «продолжить» эксперта.

---

## 7. Quality gate / employment book

### 7.1. Общий gate (уже частично в v2)

Из ТЗ-13 §5.2 + код `run_document_ingest_v2`:

- failed page **или** chars < `INGEST_MIN_CHARS_DOC` **или** маркеры `[ocr_error]`/`[ocr_empty]` → `ingest_review_required=true`.

### 7.2. Трудовая книжка (Phase 4 — обязательно)

Если `doc_type` / placement / requirement ∈ `{labor_book, labor, workbook}` (и русские алиасы в placement):

- **всегда** `ingest_review_required=true`;
- job status `needs_review` (как при review);
- авто-classify/LLM extract **не** считать финальным без accept эксперта;
- drafts `labor_timeline_drafts` можно писать, но UI помечает «черновик до сверки».

---

## 8. Security / ПДн / примирение FIO vs case_id

| Правило | Деталь |
|---------|--------|
| Disk folder naming | **Оставить as-is ТЗ-14:** `SFRFR-cases/{ФИО|uuid}/incoming|outgoing` |
| OCR resolve | **Никогда** не искать файл «по ФИО». Только `yandex_disk_path` / сохранённые segment+name из БД |
| DB paths | Хранить path строки, ключ — `document_id` / `case_id` |
| Public Disk links | Запрещены |
| Логи | `engine`, `page`, `char_count`, `source_used`, `duration_ms` — без полного OCR и без СНИЛС |
| Tracker / Wiki / Git | Без ПДн, без ФИО клиентов, без OCR-текста |
| Signed URL | Только Storage для HITL preview, короткий TTL (as-is admin) |

Конфликт «новые layout по case_id» vs «текущий FIO на Диске»: **coding ТЗ выбирает FIO layout на Диске + path-in-DB**. Миграция UUID→ФИО — отдельный ops (уже есть CLI), не часть OCR sprint.

---

## 9. Implementation phases

| Phase | Содержание | Acceptance |
|-------|------------|------------|
| **0** | Audit (этот документ + ТЗ-13 §15) | Зафиксированы gaps: Storage-only download; нет Disk download; нет path columns; нет OCRAdapter; трудовая не always-review |
| **1** | **Source resolver only** | §4.5; worker local→Disk→(Storage по флагу); движки OCR **без изменений**; без toggle `INGEST_OCR_ENGINE` |
| **2** | Job/document audit fields | Миграция колонок §3; запись paths при mirror/upload; `ocr_source_used` после resolve |
| **3** | OCRAdapter thin wrap | Protocol + wrap Vision/Tesseract/text_layer; тесты mock; confidence nullable |
| **4** | Quality gate employment book | Always `ingest_review_required` для labor_*; тест |
| **5** | Admin review gaps | Бейджи source/engine; показать `ocr_source_used`; split gaps по ТЗ-13 §8 |
| **6** | Inventory gate / bakeoff plan | Документ сравнения движков (Vision vs Tesseract vs future); **без** vendor lock; критерии смены primary — отдельно, код не обязателен |

**Первый код после аудита = Phase 1.** Не начинать Phase 3–4, пока Phase 1 зелёный.

---

## 10. File touch list (ожидаемые пути)

### Phase 1 (обязательно)

| Путь | Действие |
|------|----------|
| `src/sfrfr/services/ocr_source_resolver.py` | **новый** resolver |
| `src/sfrfr/services/document_ingest_worker.py` | `process_document_ingest_job`: resolve вместо голого Storage download; finally temp cleanup |
| `src/sfrfr/integrations/yandex_workspace/disk.py` | **добавить** download (bytes или temp) |
| `tests/unit/test_ocr_source_resolver.py` | **новый** unit с mocks |
| `tests/unit/test_document_ingest_worker_*.py` или расширить существующие | mock resolve order |

### Phase 2

| Путь | Действие |
|------|----------|
| `supabase/migrations/YYYYMMDDHHMMSS_ocr_source_paths.sql` | колонки §3 |
| `src/sfrfr/integrations/yandex_workspace/case_mirror.py` | возвращать/прокидывать paths (уже частично) |
| `src/sfrfr/services/document_ingest_worker.py` / upload path | persist `local_path`, `yandex_disk_path` |
| `src/sfrfr/services/documents_schema.py` | если нужен allow-list колонок |

### Phase 3

| Путь | Действие |
|------|----------|
| `src/sfrfr/ocr/adapter.py` | **новый** |
| `src/sfrfr/services/document_ingest_v2.py` | вызовы через adapter |
| `src/sfrfr/ocr/engine.py` | опционально facade |

### Phase 4–5

| Путь | Действие |
|------|----------|
| `src/sfrfr/services/document_ingest_v2.py` / `document_ingest.py` | labor always review |
| `src/sfrfr/api/routes/admin_portal.py` | UI/API gaps |
| cabinet admin UI (если есть отдельные tsx) | бейджи — только при явном фронтовом скоупе |

### Не трогать без нужды

- `scripts/document_ingest_worker.py` (кроме импорта, если понадобится)
- `docs/systemd/sfrfr-document-ingest.service`
- amoCRM пакеты
- Celery/Redis конфиги (их нет — не создавать)

---

## 11. Tests

Правила:

- только unit + mocks;
- **без** реальных документов клиентов, токенов OAuth, вызовов Vision/Disk/Storage;
- temp файлы чистить в тесте.

Минимум Phase 1:

| Тест | Assert |
|------|--------|
| `test_resolve_prefers_local_hash_match` | Storage download **не** вызван |
| `test_resolve_disk_temp_deleted` | после context/finally файла нет |
| `test_resolve_hash_mismatch_skips_local` | переход к следующей ветке |
| `test_resolve_storage_fallback_only_when_flag` | при false — Storage не вызван; raise |
| `test_resolve_storage_fallback_when_flag` | когда local/disk пусты и flag=true |
| `test_resolve_does_not_lookup_fio` | нет вызова `lookup_case_client_full_name` |
| `test_unresolved_raises` | fail safe |

Phase 3+: mock Vision/Tesseract; page source labels.  
Phase 4: labor → `ingest_review_required is True` даже при высоком char_count.

Команды:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ocr_source_resolver.py -q --basetemp=tmp/pytest
```

---

## 12. Env vars

Уже используемые (не ломать):

```text
INGEST_MIN_CHARS_PER_PAGE=80
INGEST_MIN_CHARS_DOC=120
INGEST_OCR_DPI=200
INGEST_MAX_PAGES=40
INGEST_OCR_ENGINE=auto
INGEST_VISION_FALLBACK_TESSERACT=true
TESSERACT_LANG=rus+eng
DOCUMENT_INGEST_ASYNC=true
DOCUMENT_WORKER_POLL_SECONDS=3
# storage
# storage_local_path / STORAGE_LOCAL_PATH → Settings.storage_local_path
YANDEX_DISK_ENABLED=true
# OAuth Disk — secrets/yandex-workspace.env (не в git)
YANDEX_VISION_API_KEY=   # или YANDEX_API_KEY
YANDEX_VISION_FOLDER_ID= # или YANDEX_FOLDER_ID
```

Опционально Phase 1–2 (канон §16 ТЗ-13):

```text
# MVP: false — Storage не обязателен для OCR-read
SUPABASE_STORAGE_OCR_FALLBACK=false
INGEST_OCR_STORAGE_FALLBACK=false   # алиас того же флага
INGEST_OCR_REQUIRE_HASH_MATCH=true  # default true если checksum_sha256 задан
```

Секреты не коммитить.

---

## 13. YDB VS Code plugin

**Вне скоупа OCR-спринта.**

Плагин/контур YDB (если упоминается в org) относится к другим задачам (например Postbox / аналитика), **не** к чтению байтов документов и не к Vision/Tesseract. В PR Phase 1–5 не подключать YDB зависимости и не писать OCR через YDB.

---

## 14. Критерии готовности (чеклист для merge кода)

### Phase 1 (must)

- [ ] Resolver local → Disk → Storage реализован и покрыт unit-тестами
- [ ] Worker больше не hardcode-only Storage download
- [ ] Temp с Диска удаляется в `finally`
- [ ] Hash mismatch не принимается молча
- [ ] Нет поиска по ФИО для OCR
- [ ] Нет Celery/Redis/новой очереди
- [ ] systemd entrypoint прежний
- [ ] Движки OCR не регрессировали (существующие unit ingest зелёные)

### Позже (не блокируют Phase 1 merge)

- [ ] Колонки path / `ocr_source_used` / `document_version`
- [ ] OCRAdapter + confidence nullable
- [ ] Employment always review
- [ ] Admin бейджи source
- [ ] Bakeoff plan Phase 6 задокументирован

### Продуктовые (сквозные, из ТЗ-13)

- [ ] LLM не как OCR
- [ ] ПДн не в Tracker/Wiki/Git/логах
- [ ] Storage остаётся для quarantine/verified/UI

---

## 15. Что делать coding-агенту прямо сейчас

1. Прочитать этот файл + ТЗ-13 §3.7 / §15.  
2. Реализовать **только Phase 1** (resolver + Disk download + worker wire + tests).  
3. Не менять движки Vision/Tesseract/text_layer.  
4. Отдельный PR/коммит на Phase 2+.  
5. После Phase 1 — короткий отчёт: какие mock-тесты зелёные, какой source_used в happy-path.

---

**Связанные документы:** [13-document-ingest-v2.md](13-document-ingest-v2.md) · [14-yandex-workspace.md](14-yandex-workspace.md) · systemd `docs/systemd/sfrfr-document-ingest.service`
